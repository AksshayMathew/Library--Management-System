"""Input validation shared by every entry point (service, CLI and API).

All regular expressions live here, and only here, so the CLI and the REST API
can never disagree about what a valid ISBN or email address looks like.
Each ``validate_*`` function returns a normalised value or raises
``ValidationError``.
"""

from __future__ import annotations

import re
from typing import Any

from library.exceptions import ValidationError

# re.ASCII: without it \d also matches non-ASCII digits such as Arabic-Indic numerals.
ISBN10_RE = re.compile(r"^\d{9}[\dX]$", re.ASCII)
ISBN13_RE = re.compile(r"^97[89]\d{10}$", re.ASCII)
ISBN_SEPARATORS_RE = re.compile(r"[\s-]")
# Local part: dot-separated atoms (no leading, trailing or double dots).
# Domain: labels that do not start or end with a hyphen, then an alphabetic TLD.
EMAIL_RE = re.compile(
    r"^[A-Za-z0-9_%+-]+(\.[A-Za-z0-9_%+-]+)*"
    r"@([A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?\.)+[A-Za-z]{2,}$"
)
EMAIL_MAX_LENGTH = 254
MEMBER_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,20}$")
EMPLOYEE_ID_RE = re.compile(r"^[A-Za-z0-9]{1,20}$")
MAX_COUNT = 10_000  # sanity cap for counts such as copies (SQLite INTEGER is 64-bit)


def normalize_isbn(raw: str) -> str:
    """Strip spaces and hyphens and upper-case a trailing ``x`` check digit."""
    return ISBN_SEPARATORS_RE.sub("", raw).upper()


def _isbn10_checksum_ok(isbn: str) -> bool:
    """ISBN-10: digits weighted 10..1 must sum to a multiple of 11 (``X`` = 10)."""
    total = sum((10 - i) * (10 if ch == "X" else int(ch)) for i, ch in enumerate(isbn))
    return total % 11 == 0


def _isbn13_checksum_ok(isbn: str) -> bool:
    """ISBN-13: digits weighted alternately 1 and 3 must sum to a multiple of 10."""
    total = sum(int(ch) * (1 if i % 2 == 0 else 3) for i, ch in enumerate(isbn))
    return total % 10 == 0


def isbn10_to_isbn13(isbn10: str) -> str:
    """Convert a valid ISBN-10 to its ISBN-13 form (``978`` prefix + new check digit)."""
    core = "978" + isbn10[:9]
    total = sum(int(ch) * (1 if i % 2 == 0 else 3) for i, ch in enumerate(core))
    return core + str((10 - total % 10) % 10)


def validate_isbn(raw: Any) -> str:
    """Return the book's canonical ISBN-13, or raise ``ValidationError``.

    The regex checks the *shape*; the checksum catches typos such as two
    swapped digits that the regex alone would accept. A valid ISBN-10 is
    converted to ISBN-13, so the same book can never be stored twice under
    its two ISBN forms, and either form finds it.
    """
    if not isinstance(raw, str):
        raise ValidationError("ISBN must be a string")
    isbn = normalize_isbn(raw)
    if ISBN10_RE.fullmatch(isbn) and _isbn10_checksum_ok(isbn):
        return isbn10_to_isbn13(isbn)
    if ISBN13_RE.fullmatch(isbn) and _isbn13_checksum_ok(isbn):
        return isbn
    raise ValidationError(f"Invalid ISBN: {raw!r}")


def validate_email(raw: Any) -> str:
    """Return the trimmed, lower-cased email address, or raise ``ValidationError``."""
    if (
        not isinstance(raw, str)
        or len(raw.strip()) > EMAIL_MAX_LENGTH
        or not EMAIL_RE.fullmatch(raw.strip())
    ):
        raise ValidationError(f"Invalid email address: {raw!r}")
    return raw.strip().lower()


def validate_member_id(raw: Any) -> str:
    """Member IDs are 1-20 letters, digits, underscores or hyphens (e.g. ``S001``)."""
    if not isinstance(raw, str) or not MEMBER_ID_RE.fullmatch(raw.strip()):
        raise ValidationError(f"Invalid member ID: {raw!r} (use 1-20 letters, digits, '_' or '-')")
    return raw.strip()


def validate_employee_id(raw: Any) -> str:
    """Employee IDs are 1-20 letters or digits (e.g. ``56040183``), surrounding spaces ignored."""
    if not isinstance(raw, str) or not EMPLOYEE_ID_RE.fullmatch(raw.strip()):
        raise ValidationError(f"Invalid Employee ID: {raw!r} (use 1-20 letters or digits)")
    return raw.strip()


def require_text(raw: Any, field: str) -> str:
    """Return ``raw`` stripped, or raise if it is missing, not a string, or blank."""
    if not isinstance(raw, str) or not raw.strip():
        raise ValidationError(f"Field '{field}' must be a non-empty string")
    return raw.strip()


def validate_positive_int(raw: Any, field: str, maximum: int = MAX_COUNT) -> int:
    """Return ``raw`` if it is an integer from 1 to ``maximum`` (booleans are rejected).

    The upper bound stops absurd values (e.g. 10**20) from overflowing SQLite's
    64-bit INTEGER column and crashing the request.
    """
    if isinstance(raw, bool) or not isinstance(raw, int) or not 1 <= raw <= maximum:
        raise ValidationError(f"Field '{field}' must be a positive integer (at most {maximum})")
    return raw
