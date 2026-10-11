"""Custom exception hierarchy for the library domain.

Every error the service layer can raise derives from ``LibraryError`` so the
CLI and the API can each handle "expected" failures in one place, while
genuine bugs (anything else) still surface loudly. These classes deliberately
know nothing about HTTP status codes or exit codes - mapping them is the job of
each delivery layer.
"""

from __future__ import annotations


class LibraryError(Exception):
    """Base class for all expected library errors."""


class ValidationError(LibraryError):
    """Raised when input data (ISBN, email, field values...) is invalid."""


class BookNotFoundError(LibraryError):
    """Raised when no book exists with the given ISBN."""

    def __init__(self, isbn: str) -> None:
        self.isbn = isbn
        super().__init__(f"No book found with ISBN {isbn}")


class MemberNotFoundError(LibraryError):
    """Raised when no member exists with the given ID."""

    def __init__(self, member_id: str) -> None:
        self.member_id = member_id
        super().__init__(f"No member found with ID {member_id!r}")


class BookNotAvailableError(LibraryError):
    """Raised when every copy of a book is already on loan."""

    def __init__(self, isbn: str) -> None:
        self.isbn = isbn
        super().__init__(f"No copies of book {isbn} are currently available")


class BorrowLimitExceededError(LibraryError):
    """Raised when a member already holds as many books as their type allows."""

    def __init__(self, member_id: str, limit: int) -> None:
        self.member_id = member_id
        self.limit = limit
        super().__init__(f"Member {member_id!r} has reached their borrow limit of {limit}")


class DuplicateBookError(LibraryError):
    """Raised when adding a book whose ISBN is already in the catalogue."""

    def __init__(self, isbn: str) -> None:
        self.isbn = isbn
        super().__init__(f"A book with ISBN {isbn} already exists")


class DuplicateMemberError(LibraryError):
    """Raised when registering a member ID that is already taken."""

    def __init__(self, member_id: str) -> None:
        self.member_id = member_id
        super().__init__(f"A member with ID {member_id!r} already exists")


class StorageError(LibraryError):
    """Raised when the database cannot be opened or a write to it fails."""


class LoanNotFoundError(LibraryError):
    """Raised when returning a book the member does not currently have on loan."""

    def __init__(self, member_id: str, isbn: str) -> None:
        self.member_id = member_id
        self.isbn = isbn
        super().__init__(f"Member {member_id!r} has no active loan for book {isbn}")
