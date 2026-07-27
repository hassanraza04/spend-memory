# Spend Memory glossary

## Terms

- **Statement document**: The immutable original file a person imports. It is never changed by parsing or enrichment.
- **Source document**: The local record of a statement document, identified by its content hash and parser version.
- **Parser**: An adapter that recognises one input format and extracts raw transactions without changing their source values.
- **Raw transaction**: One extracted statement row. Its date, description, amount text, currency text, and source location retain what the document expressed.
- **Canonical transaction**: A validated transaction used by the application. Its `amount_minor` is a non-negative integer and its `direction` states whether it is a debit or credit.
- **Source amount**: The signed amount representation used by an input statement. It remains part of the raw transaction and is not the canonical money representation.
- **Account identity**: A stable local identifier that keeps transactions from different statement accounts distinct. It is not an online banking connection.
- **Import run**: One attempt to parse a source document with a particular parser version.
- **Lineage**: The links from a displayed or derived value back to its source document, page or row, extraction method, and version.
