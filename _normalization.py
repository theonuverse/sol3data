"""Shared normalization helpers used by public models and scrapers."""
import re

_WHITESPACE = re.compile(r"\s+")
_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")
_PARENTHETICAL = re.compile(r"\(([^)]+)\)")


def normalize_text(value: str) -> str:
    return _WHITESPACE.sub(" ", value).strip()


def normalize_key(value: str) -> str:
    return normalize_text(value).casefold()


def character_slug(name: str) -> str:
    normalized = normalize_key(name)
    if not normalized:
        raise ValueError("Character name cannot be empty.")
    normalized = _PARENTHETICAL.sub(r"-\1", normalized)
    return _NON_ALPHANUMERIC.sub("-", normalized).strip("-")
