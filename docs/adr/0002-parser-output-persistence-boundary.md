# ADR 0002: Keep parser output independent from persisted record IDs

## Status

Accepted

## Context

A statement parser works only with document bytes and source details. It cannot know the identifiers later assigned to a stored source document or raw transaction. Coupling parser output to those IDs would make parsers depend on persistence and would make standalone parsing harder to test.

## Decision

`StatementParser` returns immutable `ParsedRawTransaction` values. They retain the raw source fields, page, row, text lineage, optional raw account identity, reference and balance, and extraction confidence. In particular, `amount_text` remains unchanged from the statement. When OCR safely corrects an unambiguous amount token, the parser stores that correction separately as `normalized_amount_text`.

The ingestion storage stage later creates persisted `RawTransaction` records and assigns source-document and raw-transaction IDs.

## Consequences

Parsers remain adapters for source formats and do not create database records. Storage owns persistence identifiers. Canonicalisation later derives non-negative integer minor units and explicit debit or credit direction, as defined in ADR 0001.
