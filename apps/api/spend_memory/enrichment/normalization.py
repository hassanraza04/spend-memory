from __future__ import annotations

import re

_PREFIX = re.compile(r"^(?:pos|card|debit|payment|purchase|online)\s+", re.IGNORECASE)
_TERMINAL = re.compile(
    r"\s+(?:term(?:inal)?|txn|ref|id|#)\s*[a-z0-9-]+(?=\s|$)", re.IGNORECASE
)
_TRAILING_CHANNEL = re.compile(r"\s+online$", re.IGNORECASE)
_PUNCTUATION = re.compile(r"[^a-z0-9]+")


def normalize_descriptor(value: str) -> str:
    normalized = _PREFIX.sub("", value.strip())
    normalized = _TERMINAL.sub(" ", normalized)
    normalized = _TRAILING_CHANNEL.sub("", normalized)
    normalized = _PUNCTUATION.sub(" ", normalized.lower())
    return " ".join(normalized.split())
