"""Tests for the shared regex/validation helpers."""

from __future__ import annotations

import time

import pytest

from library.exceptions import ValidationError
from library.validators import (
    require_text,
    validate_email,
    validate_employee_id,
    validate_isbn,
    validate_member_id,
    validate_positive_int,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("9780132350884", "9780132350884"),
        ("978-0-13-235088-4", "9780132350884"),  # hyphens stripped
        ("0132350882", "9780132350884"),  # ISBN-10 -> canonical ISBN-13 (same book)
        ("0306406152", "9780306406157"),
        ("0-8044-2957-x", "9780804429573"),  # ISBN-10 with X check digit, lower-case
        (" 978 0 13 235088 4 ", "9780132350884"),  # spaces
    ],
)
def test_valid_isbns_are_normalised_to_isbn13(raw: str, expected: str) -> None:
    assert validate_isbn(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "9780132350885",  # right shape, wrong checksum
        "0306406153",  # ISBN-10 with wrong checksum
        "978013235088",  # too short
        "12345",
        "97801323508AB",  # letters
        "X306406152",  # X only allowed as the last ISBN-10 character
        "٠٣٠٦٤٠٦١٥٢",  # Arabic-Indic digits
        "",
        None,
        9780132350884,  # number instead of string
    ],
)
def test_invalid_isbns_raise(raw: object) -> None:
    with pytest.raises(ValidationError):
        validate_isbn(raw)


def test_valid_email_is_trimmed_and_lowercased() -> None:
    assert validate_email("  Asha.K@Example.COM ") == "asha.k@example.com"


@pytest.mark.parametrize(
    "raw",
    ["first.last+tag@mail.example.co.in", "a_b%c@sub-domain.example.org", "x@example.museum"],
)
def test_valid_emails_accepted(raw: str) -> None:
    assert validate_email(raw) == raw.lower()


@pytest.mark.parametrize(
    "raw",
    [
        "no-at-sign.com",
        "a@b",
        "a@@b.com",
        "a b@c.com",
        "@x.com",
        "a..b@example.com",  # consecutive dots
        ".a@example.com",  # leading dot
        "a.@example.com",  # trailing dot in local part
        "a@-example.com",  # domain label starting with a hyphen
        "a@example-.com",  # domain label ending with a hyphen
        "a@example..com",  # empty domain label
        "a@example.c",  # one-letter TLD
        "a" * 250 + "@example.com",  # longer than 254 characters
        42,
    ],
)
def test_invalid_emails_raise(raw: object) -> None:
    with pytest.raises(ValidationError):
        validate_email(raw)


def test_email_regex_is_fast_on_long_hostile_input() -> None:
    """No catastrophic backtracking (ReDoS) on long near-miss input."""
    start = time.perf_counter()
    for hostile in ("a" * 50_000 + "@", "a@" + "a-" * 25_000 + "!", "a@" + "a." * 25_000 + "1"):
        with pytest.raises(ValidationError):
            validate_email(hostile)
    assert time.perf_counter() - start < 1.0


def test_member_id_rules() -> None:
    assert validate_member_id(" S001 ") == "S001"
    with pytest.raises(ValidationError):
        validate_member_id("has space")


@pytest.mark.parametrize("raw", ["56040183", " 56040183 ", "HCL123"])
def test_valid_employee_ids(raw: str) -> None:
    assert validate_employee_id(raw) == raw.strip()


@pytest.mark.parametrize("raw", ["", "   ", "56 04", "56040183!", "1" * 21, None, 56040183])
def test_invalid_employee_ids_raise(raw: object) -> None:
    with pytest.raises(ValidationError, match="Employee ID"):
        validate_employee_id(raw)


def test_require_text_rejects_blank() -> None:
    assert require_text("  Dune ", "title") == "Dune"
    with pytest.raises(ValidationError, match="title"):
        require_text("   ", "title")


@pytest.mark.parametrize("raw", [0, -1, "3", True, 2.5, None, 10_001, 10**20])
def test_positive_int_rejects_bad_values(raw: object) -> None:
    with pytest.raises(ValidationError):
        validate_positive_int(raw, "copies")


def test_positive_int_bounds() -> None:
    assert validate_positive_int(1, "copies") == 1
    assert validate_positive_int(10_000, "copies") == 10_000
    assert validate_positive_int(5, "copies", maximum=5) == 5
    with pytest.raises(ValidationError, match="at most 5"):
        validate_positive_int(6, "copies", maximum=5)
