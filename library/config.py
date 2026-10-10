"""Personalised library rules derived from an employee ID.

``get_my_library_parameters`` is the official personalisation script from the
assignment brief and is kept exactly as given. ``Settings`` wraps its output in
an immutable, typed object that the rest of the application depends on.
"""

from __future__ import annotations

import hashlib
import os
import random
from dataclasses import dataclass

DEFAULT_EMPLOYEE_ID = "56040183"
EMPLOYEE_ID_ENV_VAR = "LIBRARY_EMPLOYEE_ID"
DEFAULT_DB_PATH = "library.db"
DB_PATH_ENV_VAR = "LIBRARY_DB_PATH"
LOAN_PERIOD_DAYS = 14


def get_my_library_parameters(employee_id: str) -> dict:
    """Deterministic, unique library rules per joiner."""
    seed = int(hashlib.sha256(('lib-' + employee_id).encode()).hexdigest(), 16) % (2**31)
    rng = random.Random(seed)
    genres = ['Fiction', 'Sci-Fi', 'Biography', 'History', 'Technology',
              'Self-Help', 'Mystery', 'Poetry', 'Fantasy', 'Science']
    return {
        'genres': rng.sample(genres, 6),
        'student_borrow_limit': rng.randint(2, 4),
        'staff_borrow_limit': rng.randint(5, 8),
        'fine_per_day': round(rng.uniform(1.5, 5.0), 2),
    }


@dataclass(frozen=True)
class Settings:
    """Immutable library rules for one joiner.

    Frozen so that no layer can accidentally change a borrow limit or the fine
    rate at runtime.
    """

    employee_id: str
    genres: tuple[str, ...]
    student_borrow_limit: int
    staff_borrow_limit: int
    fine_per_day: float
    loan_period_days: int = LOAN_PERIOD_DAYS

    @classmethod
    def from_employee_id(cls, employee_id: str) -> Settings:
        """Build settings by running the personalisation script for ``employee_id``."""
        params = get_my_library_parameters(employee_id)
        return cls(
            employee_id=employee_id,
            genres=tuple(params["genres"]),
            student_borrow_limit=params["student_borrow_limit"],
            staff_borrow_limit=params["staff_borrow_limit"],
            fine_per_day=params["fine_per_day"],
        )


def load_settings(employee_id: str | None = None) -> Settings:
    """Resolve the employee ID (argument > environment variable > default) and load settings."""
    resolved = employee_id or os.environ.get(EMPLOYEE_ID_ENV_VAR) or DEFAULT_EMPLOYEE_ID
    return Settings.from_employee_id(resolved)
