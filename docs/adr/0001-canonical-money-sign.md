# ADR 0001: Store canonical money as absolute minor units and direction

## Status

Accepted

## Context

Statement formats express debits and credits in different ways. The synthetic fixtures use signed source amounts, while some future statements may use separate debit and credit columns or labels.

## Decision

Raw transactions retain the source amount exactly as extracted. Canonical transactions store a non-negative integer `amount_minor` and a separate `direction` of `debit` or `credit`.

## Consequences

Parsing is responsible for validating the source sign or column convention and deriving direction. Money calculations use the canonical fields with explicit sign rules, so no calculation relies on binary floating point or guesses a debit from a description.
