"""Start-up interaction shared by every entry point (CLI, API server, seed script).

Each one greets the user and asks for their Employee ID, which personalises
the library rules. Input and output are passed in as functions, so tests can
supply typed answers without a real keyboard.
"""

from __future__ import annotations

from collections.abc import Callable

from library.config import Settings
from library.exceptions import ValidationError
from library.validators import validate_employee_id

WELCOME_MESSAGE = "Welcome to HCLTech Library Management System"
EMPLOYEE_ID_PROMPT = "Please enter your Employee ID: "
MAX_ATTEMPTS = 3

Reader = Callable[[str], str]
Writer = Callable[[str], None]

# Invisible characters that sneak into typed or piped input: a byte-order mark
# (Windows PowerShell adds one when piping text into a program) and zero-width spaces.
INVISIBLE_CHARS = "﻿​"


def clean_input(raw: str) -> str:
    """Remove invisible characters and surrounding whitespace from one line of input."""
    return raw.translate({ord(ch): None for ch in INVISIBLE_CHARS}).strip()


def ask_employee_id(read: Reader = input, write: Writer = print, attempts: int = MAX_ATTEMPTS) -> str:
    """Ask for the Employee ID until a valid one is entered (at most ``attempts`` times).

    Raises ``ValidationError`` if no valid ID is given, including when the
    input ends (Ctrl+Z / Ctrl+D or an empty pipe) before an ID is typed.
    """
    for attempt in range(1, attempts + 1):
        try:
            raw = read(EMPLOYEE_ID_PROMPT)
        except EOFError:
            raise ValidationError("No Employee ID was entered") from None
        try:
            return validate_employee_id(clean_input(raw))
        except ValidationError as exc:
            if attempt < attempts:
                write(f"{exc}. Please try again.")
    raise ValidationError(f"No valid Employee ID after {attempts} attempts")


def describe_rules(settings: Settings) -> str:
    """One short paragraph confirming the rules that apply to this Employee ID."""
    return (
        f"Library rules for Employee ID {settings.employee_id}:\n"
        f"  Genres: {', '.join(settings.genres)}\n"
        f"  Borrow limits: student {settings.student_borrow_limit}, staff {settings.staff_borrow_limit}\n"
        f"  Fine: {settings.fine_per_day:.2f} per day after {settings.loan_period_days} days"
    )
