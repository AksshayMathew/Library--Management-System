"""Tests for the overdue fine rules (fine_per_day = 1.73 for employee 56040183)."""

from __future__ import annotations

from datetime import date

import pytest

from library.config import Settings
from library.services.fine_policy import FinePolicy

DUE = date(2026, 1, 15)


@pytest.fixture
def policy(settings: Settings) -> FinePolicy:
    return FinePolicy.from_settings(settings)


def test_policy_uses_personalised_rate(policy: FinePolicy) -> None:
    assert policy.fine_per_day == 1.73
    assert policy.loan_period_days == 14


def test_due_date_is_fourteen_days_later(policy: FinePolicy) -> None:
    assert policy.due_date(date(2026, 1, 1)) == DUE


@pytest.mark.parametrize(
    ("returned_on", "expected_fine"),
    [
        (date(2026, 1, 10), 0.0),  # early
        (DUE, 0.0),  # on the due date itself
        (date(2026, 1, 16), 1.73),  # one day late
        (date(2026, 1, 25), 17.3),  # ten days late
        (date(2026, 2, 14), 51.9),  # thirty days late
    ],
)
def test_fine_calculation(policy: FinePolicy, returned_on: date, expected_fine: float) -> None:
    assert policy.calculate(DUE, returned_on) == expected_fine


def test_days_overdue_never_negative(policy: FinePolicy) -> None:
    assert policy.days_overdue(DUE, date(2026, 1, 1)) == 0
