# Adding a parser

Spend Memory parses statements only on the local device. A parser turns one supported document into source-faithful `ParsedRawTransaction` rows. It does not calculate balances, resolve merchants, or write to storage.

1. Add a picklable parser with a stable `parser_id`, `version`, `can_parse`, `parse`, and `ParserCapabilities` value.
2. Keep dates, descriptions, and amounts as source text. Supply a source page or row and a safe `StatementParserError` for malformed input.
3. Add a `ParserFixture` and run `assert_parser_conforms(parser, fixture)` in `apps/api/tests/test_parser_conformance.py`.
4. Register a supported parser in `get_ingestion_service`. The only production entry point for document bytes is `IngestionService.import_document`.

Parser selection and parsing run in the existing isolated worker. The repository only receives typed rows after validation. Do not call storage methods directly from a parser and do not add canonical amount fields to parser output.

Receipt-image and transaction-screenshot fixture adapters are intentionally experimental. Their capability metadata sets `experimental=True`, so `ParserRegistry` excludes them even when they are manually supplied. Keep new experimental adapters out of the default registry until their safe ingress rules and synthetic conformance coverage are approved.

The import screen can preview recognized synthetic CSV source rows before a user confirms import. It is a display-only preview. The local API validates and parses the chosen file again at import time, and it never silently corrects a row.
