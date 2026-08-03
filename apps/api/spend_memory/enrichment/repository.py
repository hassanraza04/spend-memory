from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import duckdb

from spend_memory.enrichment.models import (
    Category,
    CategoryDecision,
    Counterparty,
    DuplicateCandidate,
    Merchant,
    MerchantMatch,
    RecurringCandidate,
    TrustedTransaction,
    UnusualSpendCandidate,
)
from spend_memory.enrichment.normalization import normalize_descriptor
from spend_memory.enrichment.search import SearchRow
from spend_memory.storage.repository import apply_migrations, database_write_lock

if TYPE_CHECKING:
    from spend_memory.enrichment.service import RefreshResult


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

    def create_counterparty(self, label: str) -> Counterparty:
        counterparty = Counterparty(uuid4(), _required_text(label, "label"))
        self._write(
            "INSERT INTO counterparties (counterparty_id, label) VALUES (?, ?)",
            [counterparty.counterparty_id, counterparty.label],
        )
        return counterparty

    def confirm_counterparty_alias(self, descriptor: str, counterparty_id: UUID) -> None:
        self._write(
            """
            INSERT INTO counterparty_aliases (
                counterparty_alias_id, normalized_descriptor, counterparty_id
            ) VALUES (?, ?, ?)
            ON CONFLICT (normalized_descriptor) DO UPDATE SET
                counterparty_id = excluded.counterparty_id,
                confirmed_at = now()
            """,
            [uuid4(), _normalized_descriptor(descriptor), counterparty_id],
        )

    def assign_counterparty_transactions(
        self, counterparty_id: UUID, raw_transaction_ids: list[UUID]
    ) -> None:
        with (
            database_write_lock(self.database_path),
            duckdb.connect(str(self.database_path)) as connection,
        ):
            connection.execute("BEGIN TRANSACTION")
            try:
                for raw_transaction_id in raw_transaction_ids:
                    trusted = connection.execute(
                        """
                        SELECT 1 FROM analytics.mart_transactions
                        WHERE raw_transaction_id = ?
                        """,
                        [raw_transaction_id],
                    ).fetchone()
                    if trusted is None:
                        raise ValueError("trusted_transaction_required")
                if raw_transaction_ids:
                    connection.executemany(
                        """
                        INSERT INTO transaction_counterparty_assignments (
                            transaction_counterparty_assignment_id,
                            raw_transaction_id,
                            counterparty_id
                        ) VALUES (?, ?, ?)
                        ON CONFLICT (raw_transaction_id) DO UPDATE SET
                            counterparty_id = excluded.counterparty_id,
                            confirmed_at = now()
                        """,
                        [
                            [uuid4(), raw_transaction_id, counterparty_id]
                            for raw_transaction_id in raw_transaction_ids
                        ],
                    )
                connection.execute("COMMIT")
            except BaseException:
                connection.execute("ROLLBACK")
                raise

    def find_counterparty(self, descriptor: str) -> Counterparty | None:
        with duckdb.connect(str(self.database_path), read_only=True) as connection:
            row = connection.execute(
                """
                SELECT counterparties.counterparty_id, counterparties.label
                FROM counterparty_aliases
                JOIN counterparties USING (counterparty_id)
                WHERE normalized_descriptor = ?
                """,
                [_normalized_descriptor(descriptor)],
            ).fetchone()
        return None if row is None else Counterparty(*row)

    def list_counterparty_transactions(
        self, counterparty_id: UUID
    ) -> list[TrustedTransaction]:
        try:
            with duckdb.connect(str(self.database_path), read_only=True) as connection:
                rows = connection.execute(
                    """
                    SELECT transactions.raw_transaction_id, transactions.account_identity,
                        transactions.transaction_date, transactions.description,
                        transactions.currency, transactions.amount_minor,
                        transactions.direction
                    FROM analytics.mart_transactions AS transactions
                    JOIN transaction_counterparty_assignments AS assignments
                        USING (raw_transaction_id)
                    WHERE assignments.counterparty_id = ?
                    ORDER BY transactions.transaction_date, transactions.raw_transaction_id
                    """,
                    [counterparty_id],
                ).fetchall()
        except duckdb.CatalogException as error:
            raise RuntimeError("trusted_mart_unavailable") from error
        return [
            TrustedTransaction(
                raw_transaction_id=raw_transaction_id,
                account_identity=account_identity,
                transaction_date=transaction_date,
                description=description,
                normalized_description=normalize_descriptor(description),
                currency=currency,
                amount_minor=amount_minor,
                direction=direction,
            )
            for (
                raw_transaction_id,
                account_identity,
                transaction_date,
                description,
                currency,
                amount_minor,
                direction,
            ) in rows
        ]

    def get_counterparty(self, counterparty_id: UUID) -> Counterparty | None:
        with duckdb.connect(str(self.database_path), read_only=True) as connection:
            row = connection.execute(
                "SELECT counterparty_id, label FROM counterparties WHERE counterparty_id = ?",
                [counterparty_id],
            ).fetchone()
        return None if row is None else Counterparty(*row)

    def list_search_rows(self) -> list[SearchRow]:
        try:
            with duckdb.connect(str(self.database_path), read_only=True) as connection:
                rows = connection.execute(
                    """
                    SELECT transactions.raw_transaction_id, transactions.account_identity,
                        transactions.transaction_date, transactions.description,
                        transactions.currency, transactions.amount_minor,
                        transactions.direction, transactions.category_id,
                        coalesce(categories.category_label, 'uncategorized'),
                        merchants.merchant_name,
                        coalesce(annotations.resolution_status, 'unresolved'),
                        transactions.original_filename, transactions.source_ordinal,
                        transactions.source_page, transactions.source_row,
                        transactions.source_text, transactions.extraction_confidence,
                        counterparties.label
                    FROM analytics.mart_transactions AS transactions
                    LEFT JOIN categories ON transactions.category_id = categories.category_id
                    LEFT JOIN merchants ON transactions.merchant_id = merchants.merchant_id
                    LEFT JOIN transaction_merchant_annotations AS annotations
                        ON transactions.raw_transaction_id = annotations.raw_transaction_id
                    LEFT JOIN transaction_counterparty_assignments AS assignments
                        ON transactions.raw_transaction_id = assignments.raw_transaction_id
                    LEFT JOIN counterparties ON assignments.counterparty_id = counterparties.counterparty_id
                    """
                ).fetchall()
        except duckdb.CatalogException as error:
            raise RuntimeError("trusted_mart_unavailable") from error
        return [
            SearchRow(
                transaction=TrustedTransaction(
                    raw_transaction_id, account_identity, transaction_date, description,
                    normalize_descriptor(description), currency, amount_minor, direction,
                ),
                category=CategoryDecision(category_id, category_label, "confirmed" if category_id else "unavailable"),
                merchant_name=merchant_name,
                state=state,
                source_document=source_document,
                source_ordinal=source_ordinal,
                source_page=source_page,
                source_row=source_row,
                source_text=source_text,
                extraction_confidence=extraction_confidence,
                counterparty_label=counterparty_label,
            )
            for (
                raw_transaction_id, account_identity, transaction_date, description, currency,
                amount_minor, direction, category_id, category_label, merchant_name, state,
                source_document, source_ordinal, source_page, source_row, source_text,
                extraction_confidence, counterparty_label,
            ) in rows
        ]

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

    def record_confirmed_merchant_currency(
        self, merchant_id: UUID, currency: str
    ) -> None:
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

    def save_merchant_annotation(
        self, raw_transaction_id: UUID, match: MerchantMatch
    ) -> None:
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

    def list_trusted_transactions(self) -> list[TrustedTransaction]:
        try:
            with duckdb.connect(str(self.database_path), read_only=True) as connection:
                rows = connection.execute(
                    """
                    SELECT raw_transaction_id, account_identity, transaction_date,
                        description, currency, amount_minor, direction
                    FROM analytics.mart_transactions
                    ORDER BY transaction_date, raw_transaction_id
                    """
                ).fetchall()
        except duckdb.CatalogException as error:
            raise RuntimeError("trusted_mart_unavailable") from error
        return [
            TrustedTransaction(
                raw_transaction_id=raw_transaction_id,
                account_identity=account_identity,
                transaction_date=transaction_date,
                description=description,
                normalized_description=normalize_descriptor(description),
                currency=currency,
                amount_minor=amount_minor,
                direction=direction,
            )
            for (
                raw_transaction_id,
                account_identity,
                transaction_date,
                description,
                currency,
                amount_minor,
                direction,
            ) in rows
        ]

    def replace_merchant_annotations(
        self, matches: dict[UUID, MerchantMatch]
    ) -> None:
        with (
            database_write_lock(self.database_path),
            duckdb.connect(str(self.database_path)) as connection,
        ):
            connection.execute("BEGIN TRANSACTION")
            try:
                connection.execute("DELETE FROM transaction_merchant_annotations")
                rows = [
                    [
                        raw_transaction_id,
                        match.merchant_id,
                        match.status,
                        match.confidence,
                        match.method,
                        json.dumps(match.evidence, sort_keys=True),
                        "v1",
                    ]
                    for raw_transaction_id, match in matches.items()
                ]
                if rows:
                    connection.executemany(
                        """
                        INSERT INTO transaction_merchant_annotations (
                            raw_transaction_id, merchant_id, resolution_status,
                            confidence, method, evidence_json, enrichment_version
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        rows,
                    )
                connection.execute("COMMIT")
            except BaseException:
                connection.execute("ROLLBACK")
                raise

    def record_confirmed_currencies(
        self,
        transactions: list[TrustedTransaction],
        matches: dict[UUID, MerchantMatch],
    ) -> None:
        rows = sorted(
            {
                (match.merchant_id, transaction.currency)
                for transaction in transactions
                if (match := matches[transaction.raw_transaction_id]).status
                == "confirmed"
                and match.merchant_id is not None
            },
            key=lambda row: (str(row[0]), row[1]),
        )
        if not rows:
            return
        with (
            database_write_lock(self.database_path),
            duckdb.connect(str(self.database_path)) as connection,
        ):
            connection.execute("BEGIN TRANSACTION")
            try:
                connection.executemany(
                    """
                    INSERT INTO merchant_currency_observations (merchant_id, currency)
                    VALUES (?, ?) ON CONFLICT DO NOTHING
                    """,
                    rows,
                )
                connection.execute("COMMIT")
            except BaseException:
                connection.execute("ROLLBACK")
                raise

    def replace_recurring_candidates(
        self, candidates: list[RecurringCandidate]
    ) -> None:
        with (
            database_write_lock(self.database_path),
            duckdb.connect(str(self.database_path)) as connection,
        ):
            connection.execute("BEGIN TRANSACTION")
            try:
                generation_id = uuid4()
                candidate_rows: list[list[object]] = []
                member_rows: list[list[object]] = []
                for candidate in candidates:
                    recurring_candidate_id = uuid4()
                    candidate_rows.append(
                        [
                            recurring_candidate_id,
                            generation_id,
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
                    )
                    member_rows.extend(
                        [recurring_candidate_id, raw_transaction_id]
                        for raw_transaction_id in candidate.raw_transaction_ids
                    )
                connection.execute(
                    """
                    INSERT INTO recurring_candidate_generations (
                        generation_id, candidate_count, member_count
                    ) VALUES (?, ?, ?)
                    """,
                    [generation_id, len(candidate_rows), len(member_rows)],
                )
                if candidate_rows:
                    connection.executemany(
                        """
                        INSERT INTO recurring_candidates (
                            recurring_candidate_id, generation_id, candidate_key,
                            account_identity, merchant_id, normalized_descriptor,
                            currency, direction, cadence, first_transaction_date,
                            last_transaction_date, amount_min_minor, amount_max_minor,
                            expected_next_start, expected_next_end, confidence,
                            evidence_json, status, enrichment_version
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'candidate', ?)
                        """,
                        candidate_rows,
                    )
                if member_rows:
                    connection.executemany(
                        """
                        INSERT INTO recurring_candidate_members (
                            recurring_candidate_id, raw_transaction_id
                        ) VALUES (?, ?)
                        """,
                        member_rows,
                    )
                stored_counts = connection.execute(
                    """
                    SELECT
                        count(DISTINCT c.recurring_candidate_id),
                        count(m.raw_transaction_id)
                    FROM recurring_candidate_generations g
                    LEFT JOIN recurring_candidates c USING (generation_id)
                    LEFT JOIN recurring_candidate_members m USING (recurring_candidate_id)
                    WHERE g.generation_id = ?
                    """,
                    [generation_id],
                ).fetchone()
                if stored_counts != (len(candidate_rows), len(member_rows)):
                    raise RuntimeError("recurring_generation_incomplete")
                connection.execute(
                    """
                    UPDATE recurring_candidate_state
                    SET active_generation_id = ?, updated_at = now()
                    WHERE state_key = 'active'
                    """,
                    [generation_id],
                )
                connection.execute("COMMIT")
            except BaseException:
                connection.execute("ROLLBACK")
                raise

    def replace_duplicate_candidates(
        self, candidates: list[DuplicateCandidate]
    ) -> None:
        with (
            database_write_lock(self.database_path),
            duckdb.connect(str(self.database_path)) as connection,
        ):
            connection.execute("BEGIN TRANSACTION")
            try:
                connection.execute("DELETE FROM duplicate_review_candidates")
                rows = [
                    [
                        uuid4(),
                        *sorted(candidate.raw_transaction_ids),
                        candidate.confidence,
                        json.dumps(candidate.evidence, sort_keys=True),
                        "v1",
                    ]
                    for candidate in candidates
                ]
                if rows:
                    connection.executemany(
                        """
                        INSERT INTO duplicate_review_candidates (
                            duplicate_candidate_id, first_raw_transaction_id,
                            second_raw_transaction_id, confidence, evidence_json, enrichment_version
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        rows,
                    )
                connection.execute("COMMIT")
            except BaseException:
                connection.execute("ROLLBACK")
                raise

    def replace_unusual_spend_candidates(
        self, candidates: list[UnusualSpendCandidate]
    ) -> None:
        with (
            database_write_lock(self.database_path),
            duckdb.connect(str(self.database_path)) as connection,
        ):
            connection.execute("BEGIN TRANSACTION")
            try:
                connection.execute("DELETE FROM unusual_spend_candidates")
                rows = [
                    [
                        uuid4(),
                        candidate.raw_transaction_id,
                        candidate.confidence,
                        json.dumps(candidate.evidence, sort_keys=True),
                        "v1",
                    ]
                    for candidate in candidates
                ]
                if rows:
                    connection.executemany(
                        """
                        INSERT INTO unusual_spend_candidates (
                            unusual_candidate_id, raw_transaction_id, confidence,
                            evidence_json, enrichment_version
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        rows,
                    )
                connection.execute("COMMIT")
            except BaseException:
                connection.execute("ROLLBACK")
                raise

    def summarize_refresh(
        self, matches: dict[UUID, MerchantMatch]
    ) -> RefreshResult:
        from spend_memory.enrichment.service import RefreshResult

        with duckdb.connect(str(self.database_path), read_only=True) as connection:
            recurring_count, duplicate_count, unusual_count = connection.execute(
                """
                SELECT
                    (SELECT count(*)
                     FROM recurring_candidates c
                     JOIN recurring_candidate_state s
                       ON s.active_generation_id = c.generation_id),
                    (SELECT count(*) FROM duplicate_review_candidates),
                    (SELECT count(*) FROM unusual_spend_candidates)
                """
            ).fetchone()
        status_counts = {
            status: sum(match.status == status for match in matches.values())
            for status in ("confirmed", "suggested", "unresolved")
        }
        return RefreshResult(
            transaction_count=len(matches),
            confirmed_merchant_count=status_counts["confirmed"],
            suggested_merchant_count=status_counts["suggested"],
            unresolved_merchant_count=status_counts["unresolved"],
            recurring_candidate_count=recurring_count,
            duplicate_candidate_count=duplicate_count,
            unusual_spend_candidate_count=unusual_count,
        )

    def _write(self, query: str, parameters: list[object]) -> None:
        with (
            database_write_lock(self.database_path),
            duckdb.connect(str(self.database_path)) as connection,
        ):
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
