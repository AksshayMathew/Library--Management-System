"""Small, focused capability interfaces (Interface Segregation Principle).

Rather than one large "LibraryItem" interface, each capability is its own
abstract class. A class only inherits the capabilities it really has - e.g. a
future reference-only item could be ``Searchable`` without being forced to
implement ``checkout``/``checkin``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class Borrowable(ABC):
    """Something that can be lent out and given back."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if at least one copy can be lent out."""

    @abstractmethod
    def checkout(self) -> None:
        """Mark one copy as lent out."""

    @abstractmethod
    def checkin(self) -> None:
        """Mark one copy as returned."""


class Searchable(ABC):
    """Something that can be matched against a free-text query."""

    @abstractmethod
    def matches(self, query: str) -> bool:
        """Return True if this object matches ``query``."""
