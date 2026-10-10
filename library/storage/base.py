"""Abstract storage interfaces (Dependency Inversion + Interface Segregation).

The service layer depends only on these abstractions, never on SQLite. Each
repository is small and focused on one aggregate, so a consumer that only
reads books does not depend on loan-writing methods.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import AbstractContextManager

from library.models.book import Book
from library.models.loan import Loan
from library.models.member import Member


class BookRepository(ABC):
    """Persistence operations for books."""

    @abstractmethod
    def add_book(self, book: Book) -> None:
        """Store a new book."""

    @abstractmethod
    def get_book(self, isbn: str) -> Book | None:
        """Return the book with ``isbn``, or ``None``."""

    @abstractmethod
    def update_book(self, book: Book) -> None:
        """Persist changes to an existing book."""

    @abstractmethod
    def iter_books(self) -> Iterator[Book]:
        """Lazily yield every book in the catalogue."""


class MemberRepository(ABC):
    """Persistence operations for members."""

    @abstractmethod
    def add_member(self, member: Member) -> None:
        """Store a new member."""

    @abstractmethod
    def get_member(self, member_id: str) -> Member | None:
        """Return the member with ``member_id``, or ``None``."""


class LoanRepository(ABC):
    """Persistence operations for loans."""

    @abstractmethod
    def add_loan(self, loan: Loan) -> Loan:
        """Store a new loan and return it with its generated ``loan_id``."""

    @abstractmethod
    def get_active_loan(self, member_id: str, isbn: str) -> Loan | None:
        """Return the member's unreturned loan for ``isbn``, or ``None``."""

    @abstractmethod
    def update_loan(self, loan: Loan) -> None:
        """Persist changes (return date, fine) to an existing loan."""

    @abstractmethod
    def count_active_loans(self, member_id: str) -> int:
        """Number of books the member currently holds."""

    @abstractmethod
    def iter_loans(self, member_id: str | None = None, active_only: bool = False) -> Iterator[Loan]:
        """Lazily yield loans, optionally filtered by member and/or active status."""


class TransactionManager(ABC):
    """Groups several repository writes into one all-or-nothing unit."""

    @abstractmethod
    def transaction(self) -> AbstractContextManager[None]:
        """Context manager: commit on success, roll back if an exception escapes."""


class LibraryStorage(BookRepository, MemberRepository, LoanRepository, TransactionManager, ABC):
    """Convenience composite for back-ends that implement every interface at once."""
