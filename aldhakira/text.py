from __future__ import annotations

import hashlib
import re
from collections import Counter
from typing import Iterable


TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_#@'-]{1,}|[\u0600-\u06ff]{2,}", re.I)
STOPWORDS = {
    "the", "and", "or", "for", "with", "from", "into", "onto", "that", "this", "these", "those",
    "what", "when", "where", "which", "while", "how", "why", "who", "whom", "whose", "are", "was",
    "were", "been", "being", "have", "has", "had", "will", "would", "could", "should", "can",
    "you", "your", "about", "there", "their", "they", "them", "then", "than", "also", "such",
    "في", "من", "على", "الى", "إلى", "عن", "ما", "ماذا", "كيف", "هذا", "هذه", "ذلك", "تلك",
    "الذي", "التي", "كان", "كانت", "هو", "هي", "هم", "مع", "بلا", "غير", "عند", "بين",
}
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
SECRET_RE = re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*['\"]?([A-Za-z0-9_\-]{12,})['\"]?")
OPENAI_RE = re.compile(r"sk-[A-Za-z0-9]{20,}")
PRIVATE_KEY_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S)


def normalize(text: str) -> str:
    text = text.replace("\u200f", " ").replace("\u200e", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def tokens(text: str) -> list[str]:
    return [token for token in (match.group(0).casefold() for match in TOKEN_RE.finditer(text)) if token not in STOPWORDS]


def token_counts(text: str) -> Counter[str]:
    return Counter(tokens(text))


def redact(text: str) -> tuple[str, list[dict]]:
    findings: list[dict] = []
    redacted = text
    for code, pattern, replacement in (
        ("PRIVATE_KEY", PRIVATE_KEY_RE, "[PRIVATE_KEY]"),
        ("OPENAI_KEY", OPENAI_RE, "[OPENAI_KEY]"),
        ("SECRET", SECRET_RE, "[SECRET]"),
        ("EMAIL", EMAIL_RE, "[EMAIL]"),
    ):
        for match in list(pattern.finditer(redacted)):
            value = match.group(0)
            findings.append(
                {
                    "code": code,
                    "replacement": replacement,
                    "length": len(value),
                    "fingerprint": hashlib.sha256(value.encode("utf-8", "ignore")).hexdigest()[:16],
                }
            )
        redacted = pattern.sub(replacement, redacted)
    return redacted, findings


def chunk_text(text: str, *, max_chars: int = 1400, overlap: int = 160) -> Iterable[str]:
    text = normalize(text)
    if not text:
        return
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        if end < len(text):
            split = max(text.rfind(". ", start, end), text.rfind("\n", start, end), text.rfind("،", start, end))
            if split > start + max_chars // 2:
                end = split + 1
        chunk = normalize(text[start:end])
        if chunk:
            yield chunk
        if end >= len(text):
            break
        start = max(0, end - overlap)
