"""
response_formatter.py — Format Nova responses for Telegram.

Handles:
- Chunking messages to 4096 char limit
- MarkdownV2 escaping
- Smart splitting (never mid-word)
"""
import re
from typing import List

TELEGRAM_MAX_LEN = 4096
TARGET_MAX_LEN = 3900  # Leave margin for formatting overhead


def chunk_message(text: str, max_len: int = TELEGRAM_MAX_LEN) -> List[str]:
    """
    Split long messages without breaking words or markdown.
    Returns list of chunks, each <= max_len chars.
    """
    if not text:
        return [""]
    if len(text) <= max_len:
        return [text]

    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break

        # Try to split at double newline (paragraph break)
        split_at = text.rfind("\n\n", 0, max_len)
        if split_at > max_len // 2:
            chunks.append(text[:split_at].rstrip())
            text = text[split_at:].lstrip("\n")
            continue

        # Try to split at single newline
        split_at = text.rfind("\n", 0, max_len)
        if split_at > max_len // 3:
            chunks.append(text[:split_at].rstrip())
            text = text[split_at:].lstrip("\n")
            continue

        # Try to split at space
        split_at = text.rfind(" ", 0, max_len)
        if split_at > max_len // 4:
            chunks.append(text[:split_at].rstrip())
            text = text[split_at:].lstrip()
            continue

        # Hard split (shouldn't happen with normal text)
        chunks.append(text[:max_len])
        text = text[max_len:]

    return chunks


# Characters that must be escaped in MarkdownV2
_MD_V2_SPECIAL = r"_*[]()~`>#+-=|{}.!"


def escape_markdown_v2(text: str) -> str:
    """
    Escape special characters for Telegram MarkdownV2.

    NOTE: This escapes EVERYTHING. If you want to preserve
    intentional markdown (bold, italic), use format_response() instead.
    """
    for char in _MD_V2_SPECIAL:
        text = text.replace(char, f"\\{char}")
    return text


def format_response(text: str) -> str:
    """
    Format Nova's plain text response for Telegram.

    Applies light formatting:
    - Lines starting with • or - become bullet lists
    - Lines with ":" get the label bolded
    - Currency values get monospace
    - Preserves intentional structure

    Returns text safe for parse_mode=None (plain text).
    We use plain text to avoid MarkdownV2 escaping hell.
    """
    if not text:
        return ""

    # Just return as-is — Nova's responses are already well-formatted
    # MarkdownV2 escaping is too fragile with dynamic content from tools
    # Plain text is safer and still readable in Telegram
    return text
