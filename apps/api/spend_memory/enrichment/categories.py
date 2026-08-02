from __future__ import annotations

from spend_memory.enrichment.models import (
    CategoryDecision,
    MerchantMatch,
    TrustedTransaction,
)
from spend_memory.enrichment.repository import EnrichmentRepository


class CategoryResolver:
    def __init__(self, repository: EnrichmentRepository) -> None:
        self.repository = repository

    def resolve(
        self, transaction: TrustedTransaction, merchant_match: MerchantMatch
    ) -> CategoryDecision:
        override = self.repository.find_transaction_category_override(
            transaction.raw_transaction_id
        )
        if override is not None:
            return CategoryDecision(
                override.category_id, override.category_label, "transaction_override"
            )
        if merchant_match.status == "confirmed" and merchant_match.merchant_id is not None:
            category = self.repository.find_merchant_category(merchant_match.merchant_id)
            if category is not None:
                return CategoryDecision(
                    category.category_id, category.category_label, "merchant_assignment"
                )
        return CategoryDecision(None, "Uncategorized", "none")
