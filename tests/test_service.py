"""Tests for LibraryService: borrowing rules, returns, fines and custom exceptions."""

from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest

from library.config import Settings
from library.decorators import MEMBER_REGISTRY, register_member_type
from library.exceptions import (
    BookNotAvailableError,
    BookNotFoundError,
    BorrowLimitExceededError,
    DuplicateBookError,
    DuplicateMemberError,
    LoanNotFoundError,
    MemberNotFoundError,
    ValidationError,
)
from library.models.member import Member
from library.services.library_service import LibraryService
from tests.conftest import CLEAN_CODE_ISBN, FakeClock

POETRY_ISBN = "9780140421996"


# -- borrowing limits ---------------------------------------------------------


def test_student_can_borrow_up_to_limit(service: LibraryService) -> None:
    for _ in range(3):  # student_borrow_limit = 3
        service.borrow_book("S1", CLEAN_CODE_ISBN)
    assert service.loans.count_active_loans("S1") == 3


def test_student_over_limit_raises(service: LibraryService) -> None:
    for _ in range(3):
        service.borrow_book("S1", CLEAN_CODE_ISBN)
    with pytest.raises(BorrowLimitExceededError) as excinfo:
        service.borrow_book("S1", CLEAN_CODE_ISBN)
    assert excinfo.value.limit == 3


def test_staff_has_higher_limit(service: LibraryService) -> None:
    for _ in range(7):  # staff_borrow_limit = 7
        service.borrow_book("T1", CLEAN_CODE_ISBN)
    with pytest.raises(BorrowLimitExceededError):
        service.borrow_book("T1", CLEAN_CODE_ISBN)


def test_failed_borrow_leaves_no_partial_changes(service: LibraryService) -> None:
    for _ in range(3):
        service.borrow_book("S1", CLEAN_CODE_ISBN)
    with pytest.raises(BorrowLimitExceededError):
        service.borrow_book("S1", CLEAN_CODE_ISBN)
    assert service.get_book(CLEAN_CODE_ISBN).available_copies == 7


def test_book_not_available_when_all_copies_out(service: LibraryService) -> None:
    service.add_book(POETRY_ISBN, "Leaves of Grass", "Walt Whitman", "Poetry", copies=1)
    service.borrow_book("T1", POETRY_ISBN)
    with pytest.raises(BookNotAvailableError):
        service.borrow_book("S1", POETRY_ISBN)


def test_unknown_member_raises_before_anything_runs(service: LibraryService) -> None:
    with pytest.raises(MemberNotFoundError):
        service.borrow_book("NOPE", CLEAN_CODE_ISBN)
    assert service.get_book(CLEAN_CODE_ISBN).available_copies == 10


def test_malformed_member_id_raises_validation_error(service: LibraryService) -> None:
    with pytest.raises(ValidationError):
        service.borrow_book("bad id!", CLEAN_CODE_ISBN)


def test_unknown_book_raises(service: LibraryService) -> None:
    with pytest.raises(BookNotFoundError):
        service.borrow_book("S1", "0306406152")


def test_borrow_sets_due_date(service: LibraryService) -> None:
    loan = service.borrow_book("S1", CLEAN_CODE_ISBN)
    assert (loan.due_date - loan.borrowed_on).days == 14


# -- returning and fines ------------------------------------------------------


def test_return_on_time_has_no_fine(service: LibraryService, clock: FakeClock) -> None:
    service.borrow_book("S1", CLEAN_CODE_ISBN)
    clock.advance(14)
    loan = service.return_book("S1", CLEAN_CODE_ISBN)
    assert loan.returned_on == clock.today
    assert loan.fine == 0.0
    assert service.get_book(CLEAN_CODE_ISBN).available_copies == 10


def test_late_return_charges_fine_per_day(service: LibraryService, clock: FakeClock) -> None:
    service.borrow_book("S1", CLEAN_CODE_ISBN)
    clock.advance(14 + 5)
    loan = service.return_book("S1", CLEAN_CODE_ISBN)
    assert loan.fine == round(5 * 1.73, 2) == 8.65


def test_return_frees_a_slot_under_the_limit(service: LibraryService) -> None:
    for _ in range(3):
        service.borrow_book("S1", CLEAN_CODE_ISBN)
    service.return_book("S1", CLEAN_CODE_ISBN)
    service.borrow_book("S1", CLEAN_CODE_ISBN)  # does not raise


def test_return_without_loan_raises(service: LibraryService) -> None:
    with pytest.raises(LoanNotFoundError):
        service.return_book("S1", CLEAN_CODE_ISBN)


# -- overdue report and member status -----------------------------------------


def test_iter_overdue_loans_yields_only_overdue(service: LibraryService, clock: FakeClock) -> None:
    service.borrow_book("S1", CLEAN_CODE_ISBN)
    clock.advance(10)
    service.borrow_book("T1", CLEAN_CODE_ISBN)
    clock.advance(10)  # S1's loan is 6 days late, T1's is not yet due
    overdue = list(service.iter_overdue_loans())
    assert [o.loan.member_id for o in overdue] == ["S1"]
    assert overdue[0].days_overdue == 6
    assert overdue[0].accrued_fine == round(6 * 1.73, 2)


def test_iter_overdue_loans_is_a_generator(service: LibraryService) -> None:
    assert isinstance(service.iter_overdue_loans(), Iterator)


def test_member_status_totals_recorded_and_accruing_fines(service: LibraryService, clock: FakeClock) -> None:
    service.borrow_book("S1", CLEAN_CODE_ISBN)
    service.borrow_book("S1", CLEAN_CODE_ISBN)
    clock.advance(16)  # both 2 days late
    service.return_book("S1", CLEAN_CODE_ISBN)  # records 3.46
    status = service.member_status("S1")
    assert status.borrow_limit == 3
    assert len(status.active_loans) == 1
    assert status.total_fines == round(2 * 2 * 1.73, 2)


def test_member_status_unknown_member(service: LibraryService) -> None:
    with pytest.raises(MemberNotFoundError):
        service.member_status("NOPE")


# -- catalogue and membership validation --------------------------------------


def test_duplicate_book_and_member_rejected(service: LibraryService) -> None:
    with pytest.raises(DuplicateBookError):
        service.add_book(CLEAN_CODE_ISBN, "Clean Code", "Robert C. Martin", "Technology")
    with pytest.raises(DuplicateMemberError):
        service.add_member("S1", "Other", "other@example.com", "student")


def test_genre_must_be_one_of_assigned(service: LibraryService, settings: Settings) -> None:
    with pytest.raises(ValidationError, match="not offered"):
        service.add_book(POETRY_ISBN, "Dune", "Frank Herbert", "Sci-Fi")  # not in our 6 genres
    book = service.add_book(POETRY_ISBN, "Leaves of Grass", "Walt Whitman", "poetry")
    assert book.genre == "Poetry" and book.genre in settings.genres


def test_invalid_email_rejected(service: LibraryService) -> None:
    with pytest.raises(ValidationError):
        service.add_member("S2", "Bad", "not-an-email", "student")


def test_search_by_query_and_genre(service: LibraryService) -> None:
    service.add_book(POETRY_ISBN, "Leaves of Grass", "Walt Whitman", "Poetry")
    assert [b.title for b in service.search_books(query="whitman")] == ["Leaves of Grass"]
    assert [b.title for b in service.search_books(genre="technology")] == ["Clean Code"]
    assert len(list(service.search_books())) == 2


# -- design principles ---------------------------------------------------------


@pytest.fixture
def faculty_type() -> Iterator[type[Member]]:
    """Register a brand-new member type the way a future developer would (OCP)."""

    @register_member_type("faculty")
    class Faculty(Member):
        def borrow_limit(self, settings: Settings) -> int:
            return settings.staff_borrow_limit + 3

    yield Faculty
    del MEMBER_REGISTRY["faculty"]


def test_new_member_type_works_without_changing_service(
    service: LibraryService, faculty_type: type[Member]
) -> None:
    """Open/Closed + Liskov: a new subclass plugs straight into the existing borrow logic."""
    service.add_member("F1", "Dr. Rao", "rao@example.com", "faculty")
    assert isinstance(service.members.get_member("F1"), faculty_type)
    for _ in range(10):
        service.borrow_book("F1", CLEAN_CODE_ISBN)
    with pytest.raises(BorrowLimitExceededError):
        service.borrow_book("F1", CLEAN_CODE_ISBN)


def test_borrow_and_return_are_logged(service: LibraryService, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="library"):
        service.borrow_book("S1", CLEAN_CODE_ISBN)
        with pytest.raises(LoanNotFoundError):
            service.return_book("T1", CLEAN_CODE_ISBN)
    messages = [r.getMessage() for r in caplog.records]
    assert any(m.startswith("borrow OK") for m in messages)
    assert any(m.startswith("return FAILED") for m in messages)
