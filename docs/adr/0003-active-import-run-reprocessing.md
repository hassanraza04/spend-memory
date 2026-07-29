# ADR 0003: Keep one active successful import run per document

## Status

Accepted

## Context

The same immutable statement document may be processed again when parser behavior
changes. Keeping every successful parser result provides lineage and makes parser
changes auditable, but analytics must not count transactions from several runs of
the same document.

An exact retry with the same document, parser ID, and parser version must also be
idempotent. It may arrive after a newer parser version has already become active.
The caller knows that parser identity from the import it is retrying. Selecting a
parser from an untrusted document would itself require unsafe work before the
idempotency check.

## Decision

The SHA-256 digest of the original bytes identifies a source document. A successful
combination of source document, parser ID, and parser version has one import run.
An exact retry returns that stored run without invoking the parser, inserting raw
transactions, or changing which run is active.

The production ingress accepts the known parser ID and version for an exact retry
and checks storage after validation but before it starts the isolated parser
worker. A caller that does not have a known identity uses normal parser selection
and parsing instead.

A newly successful parser ID or version creates a new run and its source-faithful
raw transactions. In the same DuckDB transaction, storage marks every older run
for that document inactive and marks the new run active. Parser versions are
opaque identifiers. Storage does not compare them as semantic versions.

Parsing and storage failures do not replace the active run. They roll back source
document, run, raw transaction, and file changes before a separate safe error
record is written.

## Consequences

All successful results remain available for audit and lineage. Normal analytics
reads only the active run, so parser reprocessing does not duplicate spend.
Retrying an inactive older parser version is a read of its existing result and
does not make it active again. Reprocessing with changed behavior therefore
requires a new parser version.

The repository owns the one-active-run invariant and updates it atomically with
the new raw rows. Callers do not infer the active run from version text or
timestamps.
