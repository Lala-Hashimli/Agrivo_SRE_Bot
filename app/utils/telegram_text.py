from __future__ import annotations

from html import escape

TELEGRAM_MESSAGE_LIMIT = 4096


def escape_html(value: str) -> str:
    return escape(value, quote=False)


def split_message(value: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    if limit < 1:
        raise ValueError("Message limit must be positive")
    if not value:
        return [""]

    chunks: list[str] = []
    remaining = value
    while len(remaining) > limit:
        boundary = remaining.rfind("\n", 0, limit + 1)
        if boundary < limit // 2:
            boundary = remaining.rfind(" ", 0, limit + 1)
        if boundary < 1:
            boundary = limit
        chunks.append(remaining[:boundary].rstrip())
        remaining = remaining[boundary:].lstrip()
    if remaining or not chunks:
        chunks.append(remaining)
    return chunks
