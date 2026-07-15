from __future__ import annotations

import re

REDACTED = "[REDACTED]"

_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"(?i)\b(authorization\s*:\s*bearer)\s+\S+"),
        rf"\1 {REDACTED}",
    ),
    (
        re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]{8,}"),
        rf"\1 {REDACTED}",
    ),
    (
        re.compile(
            r"(?i)\b(password|passwd|pwd|api[_-]?key|token|secret)"
            r"\s*[:=]\s*[^\s,;]+"
        ),
        rf"\1={REDACTED}",
    ),
    (
        re.compile(r"(?i)\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://[^\s]+"),
        REDACTED,
    ),
    (
        re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+\b"),
        REDACTED,
    ),
    (
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        REDACTED,
    ),
    (
        re.compile(r"(?<!\d)(?:\+994|0)(?:\s?\d){9}(?!\d)"),
        REDACTED,
    ),
)


def sanitize_text(value: str, *, max_length: int = 4000) -> str:
    sanitized = value[:max_length]
    for pattern, replacement in _PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized.strip()
