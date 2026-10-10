"""``LibraryService``: the single home of the library's business rules.

The CLI and the REST API both call these methods and contain no rules of
their own. The service depends only on the abstract repositories in
``library.storage.base`` (Dependency Inversion), which are injected through
the constructor together with a clock, so tests can control "today".
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import date
from typing import Any

from library.config import Settings
from library.decorators import log_action, require_member
from library.exceptions import (
    BookNotFoundError,
    BorrowLimitExceededError,
    DuplicateBookError,
    DuplicateMemberError,
    LoanNotFoundError,
    ValidationError,
)
from library.models.book import Book
from library.models.loan import Loan
from library.models.member import Member, create_member
from library.services.fine_policy import FinePolicy
from library.storage.base import (
    BookRepository,
    LibraryStorage,
    LoanRepository,
    MemberRepository,
    TransactionManager,
)
from library.validators import (
    require_text,
    validate_email,
    validate_isbn,
    validate_member_id,
    validate_positive_int,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OverdueLoan:
    """An unreturned loan past its due date, with the fine accrued so far."""

    loan: Loan
    days_overdue: int
    accrued_fine: float

    def to_dict(self) -> dict[str, Any]:
        return {**self.loan.to_dict(), "days_overdue": self.days_overdue, "accrued_fine": self.accrued_fine}


@dataclass(frozen=True)
class MemberStatus:
    """A member's details plus their current borrowing position.

    ``total_fines`` = fines recorded on returned books + fines accruing on
    books that are still out and overdue.
    """

    member: Member
    borrow_limit: int
    active_loans: list[Loan]
    total_fines: float

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.member.to_dict(),
            "borrow_limit": self.borrow_limit,
            "active_loan_count": len(self.active_loans),
            "can_borrow": len(self.active_loans) < self.borrow_limit,
            "active_loans": [loan.to_dict() for loan in self.active_loans],
            "total_fines": self.total_fines,
        }


class LibraryService:
    """Use cases of the library: catalogue, membership, borrowing and returning."""

    def __init__(
        self,
        books: BookRepository,
        members: MemberRepository,
        loans: LoanRepository,
        transactions: TransactionManager,
        settings: Settings,
        fine_policy: FinePolicy | None = None,
        today: Callable[[], date] = date.today,
    ) -> None:
        self.books = books
        self.members = members
        self.loans = loans
        self.transactions = transactions
        self.settings = settings
        self.fine_policy = fine_policy or FinePolicy.from_settings(settings)
        self._today = today

    @classmethod
    def from_storage(
        cls,
        storage: LibraryStorage,
        settings: Settings,
        today: Callable[[], date] = date.today,
    ) -> LibraryService:
        """Wire the service to a back-end that implements every repository interface."""
        return cls(storage, storage, storage, storage, settings, today=today)

    # -- catalogue ------------------------------------------------------------

    def add_book(self, isbn: str, title: str, author: str, genre: str, copies: int = 1) -> Book:
        """Validate and add a new book to the catalogue."""
        book = Book(
            isbn=validate_isbn(isbn),
            title=require_text(title, "title"),
            author=require_text(author, "author"),
            genre=self._validate_genre(genre),
            total_copies=validate_positive_int(copies, "copies"),
        )
        if self.books.get_book(book.isbn) is not None:
            raise DuplicateBookError(book.isbn)
        self.books.add_book(book)
        logger.info("Added book %s (%s), %d copies", book.isbn, book.title, book.total_copies)
        return book

    def get_book(self, isbn: str) -> Book:
        """Return the book with ``isbn`` or raise ``BookNotFoundError``."""
        isbn = validate_isbn(isbn)
        book = self.books.get_book(isbn)
        if book is None:
            raise BookNotFoundError(isbn)
        return book

    def search_books(self, query: str | None = None, genre: str | None = None) -> Iterator[Book]:
        """Generator: lazily yield books matching ``query`` and/or ``genre``."""
        for book in self.books.iter_books():
            if genre and book.genre.casefold() != genre.strip().casefold():
                continue
            if query and not book.matches(query.strip()):
                continue
            yield book

    # -- membership -----------------------------------------------------------

    def add_member(self, member_id: str, name: str, email: str, member_type: str) -> Member:
        """Validate and register a new member of the given type."""
        member = create_member(
            member_type,
            member_id=validate_member_id(member_id),
            name=require_text(name, "name"),
            email=validate_email(email),
        )
        if self.members.get_member(member.member_id) is not None:
            raise DuplicateMemberError(member.member_id)
        self.members.add_member(member)
        logger.info("Registered %s member %s", member.member_type, member.member_id)
        return member

    # -- borrowing ------------------------------------------------------------

    @log_action("borrow")
    @require_member
    def borrow_book(self, member: Member, isbn: str) -> Loan:
        """Lend one copy of ``isbn`` to the member (called as ``borrow_book(member_id, isbn)``).

        Raises ``MemberNotFoundError``, ``BookNotFoundError``,
        ``BorrowLimitExceededError`` or ``BookNotAvailableError``. The book
        update and the new loan are saved in one transaction.
        """
        with self.transactions.transaction():
            book = self.get_book(isbn)
            active_loans = self.loans.count_active_loans(member.member_id)
            if not member.can_borrow(active_loans, self.settings):
                raise BorrowLimitExceededError(member.member_id, member.borrow_limit(self.settings))
            book.checkout()
            self.books.update_book(book)
            borrowed_on = self._today()
            loan = Loan(
                loan_id=None,
                isbn=book.isbn,
                member_id=member.member_id,
                borrowed_on=borrowed_on,
                due_date=self.fine_policy.due_date(borrowed_on),
            )
            return self.loans.add_loan(loan)

    @log_action("return")
    @require_member
    def return_book(self, member: Member, isbn: str) -> Loan:
        """Return the member's copy of ``isbn`` and record any overdue fine.

        Called as ``return_book(member_id, isbn)``. Raises
        ``MemberNotFoundError`` or ``LoanNotFoundError``.
        """
        isbn = validate_isbn(isbn)
        with self.transactions.transaction():
            loan = self.loans.get_active_loan(member.member_id, isbn)
            if loan is None:
                raise LoanNotFoundError(member.member_id, isbn)
            book = self.get_book(isbn)
            book.checkin()
            self.books.update_book(book)
            loan.returned_on = self._today()
            loan.fine = self.fine_policy.calculate(loan.due_date, loan.returned_on)
            self.loans.update_loan(loan)
            return loan

    # -- reporting ------------------------------------------------------------

    def iter_overdue_loans(self) -> Iterator[OverdueLoan]:
        """Generator: yield every unreturned loan past its due date, with its fine so far.

        Loans are streamed from storage one at a time, so even a very large
        loan history is never held in memory as a full list.
        """
        today = self._today()
        for loan in self.loans.iter_loans(active_only=True):
            if loan.is_overdue(today):
                yield OverdueLoan(
                    loan=loan,
                    days_overdue=self.fine_policy.days_overdue(loan.due_date, today),
                    accrued_fine=self.fine_policy.calculate(loan.due_date, today),
                )

    @require_member
    def member_status(self, member: Member) -> MemberStatus:
        """Details, current loans and fines for a member (called as ``member_status(member_id)``)."""
        today = self._today()
        active_loans: list[Loan] = []
        total_fines = 0.0
        for loan in self.loans.iter_loans(member.member_id):
            if loan.is_active:
                active_loans.append(loan)
                total_fines += self.fine_policy.calculate(loan.due_date, today)
            else:
                total_fines += loan.fine
        return MemberStatus(
            member=member,
            borrow_limit=member.borrow_limit(self.settings),
            active_loans=active_loans,
            total_fines=round(total_fines, 2),
        )

    # -- helpers --------------------------------------------------------------

    def _validate_genre(self, genre: str) -> str:
        """Accept only the joiner's assigned genres (case-insensitive), returned in canonical form."""
        genre = require_text(genre, "genre")
        for allowed in self.settings.genres:
            if allowed.casefold() == genre.casefold():
                return allowed
        raise ValidationError(f"Genre {genre!r} is not offered (allowed: {', '.join(self.settings.genres)})")
