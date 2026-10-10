"""The ``Book`` domain model."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from library.exceptions import BookNotAvailableError, ValidationError
from library.models.interfaces import Borrowable, Searchable


@dataclass
class Book(Borrowable, Searchable):
    """A catalogue entry with one or more physical copies.

    Single Responsibility: a Book only knows about its own data and copy
    count. Input validation lives in ``validators`` and persistence in
    ``storage``.
    """

    isbn: str
    title: str
    author: str
    genre: str
    total_copies: int = 1
    available_copies: int | None = None

    def __post_init__(self) -> None:
        if self.available_copies is None:
            self.available_copies = self.total_copies

    def is_available(self) -> bool:
        """Return True if at least one copy is on the shelf."""
        return self.available_copies > 0

    def checkout(self) -> None:
        """Take one copy off the shelf, or raise ``BookNotAvailableError``."""
        if not self.is_available():
            raise BookNotAvailableError(self.isbn)
        self.available_copies -= 1

    def checkin(self) -> None:
        """Put one copy back on the shelf."""
        if self.available_copies >= self.total_copies:
            raise ValidationError(f"All copies of book {self.isbn} are already on the shelf")
        self.available_copies += 1

    def matches(self, query: str) -> bool:
        """Case-insensitive match against title, author or ISBN."""
        needle = query.casefold()
        return any(needle in field.casefold() for field in (self.title, self.author, self.isbn))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation."""
        return asdict(self)
