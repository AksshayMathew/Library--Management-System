"""Tests for the shared regex/validation helpers."""

from __future__ import annotations

import pytest

from library.exceptions import ValidationError
from library.validators import (
    require_text,
    validate_email,
    validate_isbn,
    validate_member_id,
    validate_positive_int,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("9780132350884", "9780132350884"),
        ("978-0-13-235088-4", "9780132350884"),  # hyphens stripped
        ("0306406152", "0306406152"),  # ISBN-10
        ("0-8044-2957-x", "080442957X"),  # ISBN-10 with X check digit, lower-case
    ],
)
def test_valid_isbns_are_normalised(raw: str, expected: str) -> None:
    assert validate_isbn(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "9780132350885",  # right shape, wrong checksum
        "978013235088",  # too short
        "12345",
        "97801323508AB",  # letters
        "",
        None,
    ],
)
def test_invalid_isbns_raise(raw: object) -> None:
    with pytest.raises(ValidationError):
        validate_isbn(raw)


def test_valid_email_is_trimmed_and_lowercased() -> None:
    assert validate_email("  Asha.K@Example.COM ") == "asha.k@example.com"


@pytest.mark.parametrize("raw", ["no-at-sign.com", "a@b", "a@@b.com", "a b@c.com", "@x.com", 42])
def test_invalid_emails_raise(raw: object) -> None:
    with pytest.raises(ValidationError):
        validate_email(raw)


def test_member_id_rules() -> None:
    assert validate_member_id(" S001 ") == "S001"
    with pytest.raises(ValidationError):
        validate_member_id("has space")


def test_require_text_rejects_blank() -> None:
    assert require_text("  Dune ", "title") == "Dune"
    with pytest.raises(ValidationError, match="title"):
        require_text("   ", "title")


@pytest.mark.parametrize("raw", [0, -1, "3", True, 2.5])
def test_positive_int_rejects_bad_values(raw: object) -> None:
    with pytest.raises(ValidationError):
        validate_positive_int(raw, "copies")
