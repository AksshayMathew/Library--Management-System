"""Tests for the domain models (Book, Member hierarchy, Loan)."""

from __future__ import annotations

from datetime import date

import pytest

from library.config import Settings
from library.exceptions import BookNotAvailableError, ValidationError
from library.models.book import Book
from library.models.loan import Loan
from library.models.member import Member, Staff, Student, create_member


def test_book_defaults_available_copies_to_total(sample_book: Book) -> None:
    assert sample_book.available_copies == 2
    assert sample_book.is_available()


def test_checkout_until_unavailable_then_raises(sample_book: Book) -> None:
    sample_book.checkout()
    sample_book.checkout()
    assert not sample_book.is_available()
    with pytest.raises(BookNotAvailableError):
        sample_book.checkout()


def test_checkin_cannot_exceed_total(sample_book: Book) -> None:
    sample_book.checkout()
    sample_book.checkin()
    with pytest.raises(ValidationError):
        sample_book.checkin()


@pytest.mark.parametrize("query", ["clean", "MARTIN", "978013"])
def test_book_matches_title_author_or_isbn(sample_book: Book, query: str) -> None:
    assert sample_book.matches(query)


def test_member_is_abstract() -> None:
    with pytest.raises(TypeError):
        Member("X1", "Nobody", "x@y.com")  # type: ignore[abstract]


def test_borrow_limits_are_polymorphic(settings: Settings) -> None:
    student = Student("S1", "Asha", "asha@example.com")
    staff = Staff("T1", "Ravi", "ravi@example.com")
    assert student.borrow_limit(settings) == settings.student_borrow_limit == 3
    assert staff.borrow_limit(settings) == settings.staff_borrow_limit == 7


def test_can_borrow_respects_limit(settings: Settings) -> None:
    student = Student("S1", "Asha", "asha@example.com")
    assert student.can_borrow(2, settings)
    assert not student.can_borrow(3, settings)


def test_create_member_factory() -> None:
    member = create_member("Staff", "T1", "Ravi", "ravi@example.com")
    assert isinstance(member, Staff)
    assert member.to_dict()["member_type"] == "staff"
    with pytest.raises(ValidationError, match="Unknown member type"):
        create_member("alien", "A1", "Zed", "zed@example.com")


def test_loan_overdue_only_after_due_date() -> None:
    loan = Loan(None, "9780132350884", "S1", date(2026, 1, 1), date(2026, 1, 15))
    assert not loan.is_overdue(date(2026, 1, 15))
    assert loan.is_overdue(date(2026, 1, 16))
    loan.returned_on = date(2026, 1, 20)
    assert not loan.is_overdue(date(2026, 1, 30))
