# Architecture

## Enrichment

Enrichment reads reconciled analytics marts and writes local annotations. Confirmed aliases and category assignments can affect analytical labels. Suggestions, recurring candidates, possible duplicates, and unusual-spend candidates remain review signals and never change a transaction or a total. The period explanation engine uses integer minor units and fixed templates. Milestone 5 will expose these local services through API routes.

Recurring candidate refreshes use immutable generations. Candidate and source-transaction membership rows are stored and validated before one active-generation pointer is changed. Analytics joins through that pointer, which keeps a failed refresh from exposing partial or missing lineage. Prior generations remain local and intact for recovery.
