# Spend Memory glossary

## Terms

- **Statement document**: The immutable original bytes a person imports. Parsing and enrichment never change these bytes.
- **Source document record**: The persisted metadata and storage path for one statement document. Its identity is the SHA-256 hash of the original bytes. Parser version belongs to an import run, not to this record.
- **Parser**: An adapter that recognises one input format and extracts raw transactions without changing their source values.
- **Raw transaction**: One extracted statement row. Its date, description, `amount_text`, currency text, and source location retain what the document expressed.
- **Normalized amount text**: An optional corrected OCR token stored in `normalized_amount_text`. It never replaces the source-faithful `amount_text`.
- **Canonical transaction**: A validated transaction used by the application. Its `amount_minor` is a non-negative integer and its `direction` states whether it is a debit or credit.
- **Source amount**: The signed amount representation used by an input statement. It remains part of the raw transaction and is not the canonical money representation.
- **Account identity**: A stable local identifier that keeps transactions from different statement accounts distinct. It is not an online banking connection.
- **Import run**: One attempt to parse a source document record with a particular parser version.
- **Safe statement ingress**: `IngestionService.import_document` is the only production entry point for untrusted statement bytes. It validates input, isolates parser work, and hands typed parser output to storage. Native PDF and OCR helpers are private to that worker boundary.
- **Lineage**: The links from a displayed or derived value back to its source document, page or row, extraction method, and version.
