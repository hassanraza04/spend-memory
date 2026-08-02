from __future__ import annotations

from dataclasses import dataclass

from spend_memory.enrichment.merchants import MerchantResolver
from spend_memory.enrichment.recurring import detect_recurring_candidates
from spend_memory.enrichment.repository import EnrichmentRepository
from spend_memory.enrichment.review import (
    find_duplicate_candidates,
    find_unusual_spend_candidates,
)


@dataclass(frozen=True)
class RefreshResult:
    transaction_count: int
    confirmed_merchant_count: int
    suggested_merchant_count: int
    unresolved_merchant_count: int
    recurring_candidate_count: int
    duplicate_candidate_count: int
    unusual_spend_candidate_count: int


class EnrichmentService:
    def __init__(self, repository: EnrichmentRepository) -> None:
        self.repository = repository
        self.merchant_resolver = MerchantResolver(repository)

    def refresh(self) -> RefreshResult:
        transactions = self.repository.list_trusted_transactions()
        matches = {
            transaction.raw_transaction_id: self.merchant_resolver.resolve(transaction)
            for transaction in transactions
        }
        self.repository.replace_merchant_annotations(matches)
        self.repository.record_confirmed_currencies(transactions, matches)
        self.repository.replace_recurring_candidates(
            detect_recurring_candidates(transactions, matches)
        )
        self.repository.replace_duplicate_candidates(
            find_duplicate_candidates(transactions, matches)
        )
        self.repository.replace_unusual_spend_candidates(
            find_unusual_spend_candidates(transactions, matches)
        )
        return self.repository.summarize_refresh(matches)
