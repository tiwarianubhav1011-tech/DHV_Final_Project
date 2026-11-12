"""Helpers for cleaning raw LLM output before it is used."""

import re

_THINK = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)
_UNCLOSED_THINK = re.compile(r"^.*?</think>", re.IGNORECASE | re.DOTALL)
_FENCE = re.compile(r"```(?:sql|postgresql|postgres)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
_SQL_START = re.compile(r"\b(WITH|SELECT)\b", re.IGNORECASE)
_UNSUPPORTED = re.compile(r"\bUNSUPPORTED[_ ]QUESTION\b", re.IGNORECASE)


def clean_llm_text(text: str | None) -> str:
    """Remove reasoning blocks and surrounding whitespace."""
    if not text:
        return ""
    text = _THINK.sub("", text)
    if "</think>" in text.casefold():
        text = _UNCLOSED_THINK.sub("", text)
    return text.strip()


def is_unsupported(text: str) -> bool:
    cleaned = clean_llm_text(text)
    return bool(_UNSUPPORTED.search(cleaned)) and not _SQL_START.search(
        _UNSUPPORTED.sub("", cleaned)
    )


def extract_sql(text: str) -> str:
    """Pull a single SQL statement out of an LLM reply."""
    cleaned = clean_llm_text(text)
    fence = _FENCE.search(cleaned)
    if fence:
        cleaned = fence.group(1)
    cleaned = cleaned.replace("```", "")
    match = _SQL_START.search(cleaned)
    if match:
        cleaned = cleaned[match.start():]
    # Drop anything after the first statement terminator and trailing prose.
    cleaned = cleaned.split(";")[0]
    cleaned = re.split(r"\n\s*\n(?=[A-Za-z])(?!\s*(?:SELECT|WITH|FROM|WHERE|AND|OR|ORDER|GROUP|LIMIT|JOIN|HAVING|UNION)\b)", cleaned)[0]
    # Remove SQL comments.
    cleaned = re.sub(r"--[^\n]*", "", cleaned)
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)
    return cleaned.strip()

