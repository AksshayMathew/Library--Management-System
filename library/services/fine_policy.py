"""Overdue fine calculation, kept separate from the rest of the service logic."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from library.config import Settings


@dataclass(frozen=True)
class FinePolicy:
    """Computes due dates and overdue fines.

    Isolating this rule in its own class means a different policy (e.g. a
    capped fine, or a grace period) can be swapped in without touching the
    borrowing logic.
    """

    fine_per_day: float
    loan_period_days: int = 14

    @classmethod
    def from_settings(cls, settings: Settings) -> FinePolicy:
        """Build the policy from the joiner's personalised settings."""
        return cls(fine_per_day=settings.fine_per_day, loan_period_days=settings.loan_period_days)

    def due_date(self, borrowed_on: date) -> date:
        """Date by which a book borrowed on ``borrowed_on`` must be returned."""
        return borrowed_on + timedelta(days=self.loan_period_days)

    def days_overdue(self, due_date: date, on: date) -> int:
        """Whole days past ``due_date`` as of ``on`` (never negative)."""
        return max(0, (on - due_date).days)

    def calculate(self, due_date: date, returned_on: date) -> float:
        """Fine owed for a book returned on ``returned_on``, rounded to 2 decimals."""
        return round(self.days_overdue(due_date, returned_on) * self.fine_per_day, 2)
