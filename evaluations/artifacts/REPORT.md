# Spend Memory evaluation report

This report uses only the repository's immutable synthetic fixtures. It never reads user data.

![Quality chart](quality.svg)

## Quality

| Area | Measure | Result |
| --- | --- | ---: |
| Extraction | Field precision / recall | 100% / 100% |
| Extraction | Exact amount accuracy | 100% |
| Extraction | Reconciliation rate | 100% |
| Merchant resolution | Precision / recall / coverage | 100% / 100% / 100% |
| Merchant resolution | Top-1 accuracy / calibration error | 100% / 15.7% |
| Recurring detection | Precision / recall | 100% / 100% |
| Duplicate review | Precision at threshold | 100% |
| Search | Recall@5 / MRR / structured correctness | 100% / 100% / 100% |

## Runtime

| Measure | Result |
| --- | ---: |
| Local import time | 2063.13 ms |
| OCR time | not measured |
| Index time | not applicable |
| 50-query search time | 0.59 ms |
| Peak process RSS | 140384 KiB |

## Baselines

The held-out merchant resolver is compared with exact alias matching. Its precision is 100%, versus 0% for the baseline. Search is evaluated as the current local lexical baseline because the product has no semantic index.

## Known failures

None in this synthetic run.

## Known limitations

- The image-only OCR fixture is exploratory and has no immutable ledger label.
- Category learning and semantic indexing are deliberately not product features yet.
- Runtime numbers are local-machine measurements, not performance guarantees.
