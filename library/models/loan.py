"""The ``Loan`` domain model: one member borrowing one copy of one book."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass
class Loan:
    """A borrowing record. ``returned_on`` is ``None`` while the book is still out."""

    loan_id: int | None
    isbn: str
    member_id: str
    borrowed_on: date
    due_date: date
    returned_on: date | None = None
    fine: float = 0.0

    @property
    def is_active(self) -> bool:
        """True while the book has not been returned."""
        return self.returned_on is None

    def is_overdue(self, today: date) -> bool:
        """True if the book is still out after its due date."""
        return self.is_active and today > self.due_date

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation (dates as ISO strings)."""
        return {
            "loan_id": self.loan_id,
            "isbn": self.isbn,
            "member_id": self.member_id,
            "borrowed_on": self.borrowed_on.isoformat(),
            "due_date": self.due_date.isoformat(),
            "returned_on": self.returned_on.isoformat() if self.returned_on else None,
            "fine": self.fine,
        }
