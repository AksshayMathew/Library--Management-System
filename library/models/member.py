"""Member hierarchy: an abstract ``Member`` with ``Student`` and ``Staff`` subtypes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar

from library.config import Settings
from library.decorators import MEMBER_REGISTRY, register_member_type
from library.exceptions import ValidationError


@dataclass
class Member(ABC):
    """Abstract base class for every kind of library member.

    The contract every subclass must fulfil is ``borrow_limit``. The limit is
    read from the joiner's ``Settings`` passed in by the service, so the model
    never hard-codes personalised numbers and never touches storage.
    """

    member_id: str
    name: str
    email: str

    member_type: ClassVar[str] = "member"

    @abstractmethod
    def borrow_limit(self, settings: Settings) -> int:
        """Maximum number of books this member may hold at the same time."""

    def can_borrow(self, active_loans: int, settings: Settings) -> bool:
        """Return True if the member may take one more book.

        Works identically for every subclass (Liskov Substitution): the
        service never needs to check which concrete type it is dealing with.
        """
        return active_loans < self.borrow_limit(settings)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation."""
        return {
            "member_id": self.member_id,
            "name": self.name,
            "email": self.email,
            "member_type": self.member_type,
        }


@register_member_type("student")
class Student(Member):
    """A student member, limited by the joiner's ``student_borrow_limit``."""

    def borrow_limit(self, settings: Settings) -> int:
        return settings.student_borrow_limit


@register_member_type("staff")
class Staff(Member):
    """A staff member, limited by the joiner's ``staff_borrow_limit``."""

    def borrow_limit(self, settings: Settings) -> int:
        return settings.staff_borrow_limit


def create_member(member_type: str, member_id: str, name: str, email: str) -> Member:
    """Factory: build the registered ``Member`` subclass for ``member_type``.

    New member types register themselves with ``@register_member_type``, so
    this function never needs to change (Open/Closed Principle).
    """
    try:
        member_cls = MEMBER_REGISTRY[member_type.strip().lower()]
    except (KeyError, AttributeError):
        allowed = ", ".join(sorted(MEMBER_REGISTRY))
        raise ValidationError(f"Unknown member type {member_type!r} (allowed: {allowed})") from None
    return member_cls(member_id=member_id, name=name, email=email)
