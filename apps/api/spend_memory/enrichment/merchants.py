from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from math import log, sqrt
from uuid import UUID

from spend_memory.enrichment.models import (
    Merchant,
    MerchantEvaluation,
    MerchantMatch,
    TrustedTransaction,
)
from spend_memory.enrichment.normalization import normalize_descriptor
from spend_memory.enrichment.repository import EnrichmentRepository

_SUGGESTION_THRESHOLD = 0.82
_CURRENCY_BONUS = 0.03


@dataclass(frozen=True)
class MerchantCorpusEntry:
    merchant_id: UUID
    merchant_name: str
    alias: str


def retrieval_corpus(
    examples: Iterable[tuple[UUID, str, str]], held_out_merchant_ids: set[UUID]
) -> list[MerchantCorpusEntry]:
    examples = list(examples)
    return [
        *_alias_entries(examples, held_out_merchant_ids),
        *_canonical_merchant_entries(examples),
    ]


def _alias_entries(
    examples: Iterable[tuple[UUID, str, str]], held_out_merchant_ids: set[UUID]
) -> list[MerchantCorpusEntry]:
    return [
        MerchantCorpusEntry(merchant_id, merchant_name, normalize_descriptor(descriptor))
        for merchant_id, merchant_name, descriptor in examples
        if merchant_id not in held_out_merchant_ids
    ]


class MerchantResolver:
    def __init__(self, repository: EnrichmentRepository) -> None:
        self.repository = repository

    def resolve(self, transaction: TrustedTransaction) -> MerchantMatch:
        normalized = normalize_descriptor(transaction.normalized_description)
        exact = self.repository.find_confirmed_alias(normalized)
        if exact is not None:
            return MerchantMatch(
                exact.merchant_id,
                exact.merchant_name,
                "confirmed",
                1.0,
                "confirmed_alias",
                {"normalized_descriptor": normalized},
            )

        candidates = self.repository.confirmed_merchant_candidates()
        if not candidates:
            return _unresolved(normalized)
        documents = [alias for _, alias in candidates]
        weights = _tfidf_weights(documents)
        query = _weighted_trigrams(normalized, weights)
        currencies = self.repository.confirmed_merchant_currencies()
        best: tuple[Merchant, str, float, float, bool] | None = None
        for merchant, alias in candidates:
            text_score = _cosine(query, _weighted_trigrams(alias, weights))
            currency_compatible = (merchant.merchant_id, transaction.currency) in currencies
            score = min(1.0, text_score + (_CURRENCY_BONUS if currency_compatible else 0.0))
            if best is None or score > best[2]:
                best = merchant, alias, score, text_score, currency_compatible
        assert best is not None
        merchant, alias, score, text_score, currency_compatible = best
        evidence: dict[str, str | float] = {
            "normalized_descriptor": normalized,
            "winning_alias": alias,
            "text_score": text_score,
        }
        if currency_compatible:
            evidence["currency_signal"] = "compatible"
        if score >= _SUGGESTION_THRESHOLD:
            return MerchantMatch(
                merchant.merchant_id,
                merchant.merchant_name,
                "suggested",
                round(score, 4),
                "char_ngram_tfidf",
                evidence,
            )
        return _unresolved(normalized)


def evaluate_merchant_matches(
    examples: Iterable[tuple[UUID, str, str]], held_out_merchant_ids: set[UUID]
) -> MerchantEvaluation:
    examples = list(examples)
    alias_corpus = _alias_entries(examples, held_out_merchant_ids)
    corpus = retrieval_corpus(examples, held_out_merchant_ids)
    held_out_examples = [
        example for example in examples if example[0] in held_out_merchant_ids
    ]
    metrics = _evaluation_metrics(
        held_out_examples, lambda value: _resolve_corpus(value, corpus)
    )
    baseline = _evaluation_metrics(
        held_out_examples, lambda value: _resolve_exact_alias(value, alias_corpus)
    )
    return MerchantEvaluation(
        *metrics,
        *baseline,
    )


def _canonical_merchant_entries(
    examples: Iterable[tuple[UUID, str, str]],
) -> list[MerchantCorpusEntry]:
    canonical_names = {
        merchant_id: merchant_name
        for merchant_id, merchant_name, _ in examples
    }
    return [
        MerchantCorpusEntry(
            merchant_id,
            merchant_name,
            normalize_descriptor(merchant_name),
        )
        for merchant_id, merchant_name in canonical_names.items()
    ]


def _evaluation_metrics(
    examples: list[tuple[UUID, str, str]],
    resolve: Callable[[str], tuple[UUID, float] | None],
) -> tuple[float, float, float, float]:
    correct = covered = predictions = 0
    buckets = [(0, 0, 0.0) for _ in range(5)]
    for merchant_id, _, descriptor in examples:
        match = resolve(normalize_descriptor(descriptor))
        if match is None:
            continue
        predicted_id, confidence = match
        predictions += 1
        covered += 1
        is_correct = predicted_id == merchant_id
        correct += is_correct
        index = min(4, int(confidence * 5))
        total, accurate, confidence_total = buckets[index]
        buckets[index] = total + 1, accurate + is_correct, confidence_total + confidence
    ece = (
        sum(
            total / len(examples) * abs((accurate / total) - (confidence_total / total))
            for total, accurate, confidence_total in buckets
            if total
        )
        if examples
        else 0.0
    )
    return (
        correct / predictions if predictions else 0.0,
        correct / len(examples) if examples else 0.0,
        covered / len(examples) if examples else 0.0,
        ece,
    )


def _resolve_exact_alias(
    normalized: str, corpus: list[MerchantCorpusEntry]
) -> tuple[UUID, float] | None:
    exact = next((entry for entry in corpus if entry.alias == normalized), None)
    return None if exact is None else (exact.merchant_id, 1.0)


def _resolve_corpus(
    normalized: str, corpus: list[MerchantCorpusEntry]
) -> tuple[UUID, float] | None:
    exact = next((entry for entry in corpus if entry.alias == normalized), None)
    if exact is not None:
        return exact.merchant_id, 1.0
    if not corpus:
        return None
    weights = _tfidf_weights([entry.alias for entry in corpus])
    query = _weighted_trigrams(normalized, weights)
    entry = max(corpus, key=lambda item: _cosine(query, _weighted_trigrams(item.alias, weights)))
    score = _cosine(query, _weighted_trigrams(entry.alias, weights))
    return (entry.merchant_id, score) if score >= _SUGGESTION_THRESHOLD else None


def _tfidf_weights(documents: list[str]) -> dict[str, float]:
    document_count = len(documents)
    frequencies = Counter(gram for document in documents for gram in set(_trigrams(document)))
    return {gram: log((document_count + 1) / (count + 1)) + 1 for gram, count in frequencies.items()}


def _weighted_trigrams(value: str, weights: dict[str, float]) -> Counter[str]:
    return Counter({gram: count * weights.get(gram, 1.0) for gram, count in Counter(_trigrams(value)).items()})


def _trigrams(value: str) -> list[str]:
    value = f"  {value}  "
    return [value[index : index + 3] for index in range(len(value) - 2)]


def _cosine(left: Counter[str], right: Counter[str]) -> float:
    denominator = sqrt(
        sum(value * value for value in left.values())
        * sum(value * value for value in right.values())
    )
    return (
        sum(value * right.get(key, 0) for key, value in left.items()) / denominator
        if denominator
        else 0.0
    )


def _unresolved(normalized: str) -> MerchantMatch:
    return MerchantMatch(None, None, "unresolved", 0.0, "none", {"normalized_descriptor": normalized})
