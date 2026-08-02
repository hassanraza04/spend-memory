from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID, uuid4

import duckdb

from spend_memory.enrichment.models import (
    Category,
    Merchant,
    MerchantMatch,
    RecurringCandidate,
)
from spend_memory.enrichment.normalization import normalize_descriptor
from spend_memory.storage.repository import apply_migrations, database_write_lock


class EnrichmentRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)
        apply_migrations(self.database_path)

    def create_merchant(self, merchant_name: str) -> Merchant:
        merchant = Merchant(uuid4(), _required_text(merchant_name, "merchant_name"))
        self._write(
            "INSERT INTO merchants (merchant_id, merchant_name) VALUES (?, ?)",
            [merchant.merchant_id, merchant.merchant_name],
        )
        return merchant

    def confirm_alias(self, descriptor: str, merchant_id: UUID) -> None:
        self._write(
            """
            INSERT INTO merchant_aliases (merchant_alias_id, normalized_descriptor, merchant_id)
            VALUES (?, ?, ?)
            ON CONFLICT (normalized_descriptor) DO UPDATE SET
                merchant_id = excluded.merchant_id,
                confirmed_at = now()
            """,
            [uuid4(), _normalized_descriptor(descriptor), merchant_id],
        )

    def record_confirmed_merchant_currency(self, merchant_id: UUID, currency: str) -> None:
        self._write(
            """
            INSERT INTO merchant_currency_observations (merchant_id, currency)
            VALUES (?, ?) ON CONFLICT DO NOTHING
            """,
            [merchant_id, _required_text(currency, "currency")],
        )

    def find_confirmed_alias(self, descriptor: str) -> Merchant | None:
        with duckdb.connect(str(self.database_path), read_only=True) as connection:
            row = connection.execute(
                """
                SELECT merchants.merchant_id, merchants.merchant_name
                FROM merchant_aliases JOIN merchants USING (merchant_id)
                WHERE normalized_descriptor = ?
                """,
                [_normalized_descriptor(descriptor)],
            ).fetchone()
        return None if row is None else Merchant(*row)

    def confirmed_merchant_candidates(self) -> list[tuple[Merchant, str]]:
        with duckdb.connect(str(self.database_path), read_only=True) as connection:
            rows = connection.execute(
                """
                SELECT merchants.merchant_id, merchants.merchant_name,
                    merchant_aliases.normalized_descriptor
                FROM merchant_aliases JOIN merchants USING (merchant_id)
                UNION ALL
                SELECT merchant_id, merchant_name, merchant_name FROM merchants
                """
            ).fetchall()
        return [
            (Merchant(merchant_id, name), normalize_descriptor(alias))
            for merchant_id, name, alias in rows
        ]

    def confirmed_merchant_currencies(self) -> set[tuple[UUID, str]]:
        with duckdb.connect(str(self.database_path), read_only=True) as connection:
            rows = connection.execute(
                "SELECT merchant_id, currency FROM merchant_currency_observations"
            ).fetchall()
        return set(rows)

    def create_category(self, category_label: str) -> Category:
        category = Category(uuid4(), _required_text(category_label, "category_label"))
        self._write(
            "INSERT INTO categories (category_id, category_label) VALUES (?, ?)",
            [category.category_id, category.category_label],
        )
        return category

    def assign_merchant_category(self, merchant_id: UUID, category_id: UUID) -> None:
        self._write(
            """
            INSERT INTO merchant_category_assignments (merchant_id, category_id)
            VALUES (?, ?)
            ON CONFLICT (merchant_id) DO UPDATE SET
                category_id = excluded.category_id, confirmed_at = now()
            """,
            [merchant_id, category_id],
        )

    def find_merchant_category(self, merchant_id: UUID) -> Category | None:
        with duckdb.connect(str(self.database_path), read_only=True) as connection:
            row = connection.execute(
                """
                SELECT categories.category_id, categories.category_label
                FROM merchant_category_assignments
                JOIN categories USING (category_id)
                WHERE merchant_id = ?
                """,
                [merchant_id],
            ).fetchone()
        return None if row is None else Category(*row)

    def set_transaction_category_override(
        self, raw_transaction_id: UUID, category_id: UUID
    ) -> None:
        self._write(
            """
            INSERT INTO transaction_category_overrides (raw_transaction_id, category_id)
            VALUES (?, ?)
            ON CONFLICT (raw_transaction_id) DO UPDATE SET
                category_id = excluded.category_id, confirmed_at = now()
            """,
            [raw_transaction_id, category_id],
        )

    def find_transaction_category_override(
        self, raw_transaction_id: UUID
    ) -> Category | None:
        with duckdb.connect(str(self.database_path), read_only=True) as connection:
            row = connection.execute(
                """
                SELECT categories.category_id, categories.category_label
                FROM transaction_category_overrides
                JOIN categories USING (category_id)
                WHERE raw_transaction_id = ?
                """,
                [raw_transaction_id],
            ).fetchone()
        return None if row is None else Category(*row)

    def save_merchant_annotation(self, raw_transaction_id: UUID, match: MerchantMatch) -> None:
        self._write(
            """
            INSERT INTO transaction_merchant_annotations (
                raw_transaction_id, merchant_id, resolution_status, confidence,
                method, evidence_json, enrichment_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (raw_transaction_id) DO UPDATE SET
                merchant_id = excluded.merchant_id,
                resolution_status = excluded.resolution_status,
                confidence = excluded.confidence,
                method = excluded.method,
                evidence_json = excluded.evidence_json,
                enrichment_version = excluded.enrichment_version,
                updated_at = now()
            """,
            [
                raw_transaction_id,
                match.merchant_id,
                match.status,
                match.confidence,
                match.method,
                json.dumps(match.evidence, sort_keys=True),
                "v1",
            ],
        )

    def replace_recurring_candidates(self, candidates: list[RecurringCandidate]) -> None:
        with database_write_lock(self.database_path), duckdb.connect(
            str(self.database_path)
        ) as connection:
            connection.execute("BEGIN TRANSACTION")
            try:
                connection.execute("DELETE FROM recurring_candidates")
                connection.executemany(
                    """
                    INSERT INTO recurring_candidates (
                        recurring_candidate_id, candidate_key, account_identity, merchant_id,
                        normalized_descriptor, currency, direction, cadence,
                        first_transaction_date, last_transaction_date, amount_min_minor,
                        amount_max_minor, expected_next_start, expected_next_end, confidence,
                        evidence_json, status, enrichment_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'candidate', ?)
                    """,
                    [
                        [
                            uuid4(),
                            candidate.candidate_key,
                            candidate.account_identity,
                            candidate.merchant_id,
                            candidate.normalized_descriptor,
                            candidate.currency,
                            candidate.direction,
                            candidate.cadence,
                            candidate.first_transaction_date,
                            candidate.last_transaction_date,
                            candidate.amount_min_minor,
                            candidate.amount_max_minor,
                            candidate.expected_next_start,
                            candidate.expected_next_end,
                            candidate.confidence,
                            json.dumps(candidate.evidence, sort_keys=True),
                            "v1",
                        ]
                        for candidate in candidates
                    ],
                )
                connection.execute("COMMIT")
            except BaseException:
                connection.execute("ROLLBACK")
                raise

    def _write(self, query: str, parameters: list[object]) -> None:
        with database_write_lock(self.database_path), duckdb.connect(
            str(self.database_path)
        ) as connection:
            connection.execute("BEGIN TRANSACTION")
            try:
                connection.execute(query, parameters)
                connection.execute("COMMIT")
            except BaseException:
                connection.execute("ROLLBACK")
                raise


def _required_text(value: str, field: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{field}_required")
    return value


def _normalized_descriptor(descriptor: str) -> str:
    return _required_text(normalize_descriptor(descriptor), "descriptor")
