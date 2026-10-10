"""Reusable decorators.

* ``log_action``          - logs every call of a service operation and its outcome.
* ``require_member``      - looks the member up first and fails fast if they don't exist.
* ``register_member_type`` - class decorator that plugs a new Member subclass into
  the factory without editing any existing code (Open/Closed Principle).
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from typing import Any, TypeVar

from library.exceptions import LibraryError, MemberNotFoundError
from library.validators import validate_member_id

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])
C = TypeVar("C", bound=type)

MEMBER_REGISTRY: dict[str, type] = {}


def log_action(action: str) -> Callable[[F], F]:
    """Log ``action`` with its arguments and whether it succeeded or failed.

    Intended for service methods: the first positional argument (``self``)
    is left out of the log line. Expected failures (``LibraryError``) are
    logged as warnings and re-raised unchanged.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            call_args = ", ".join([*map(repr, args[1:]), *(f"{k}={v!r}" for k, v in kwargs.items())])
            try:
                result = func(*args, **kwargs)
            except LibraryError as exc:
                logger.warning("%s FAILED (%s): %s", action, call_args, exc)
                raise
            logger.info("%s OK (%s)", action, call_args)
            return result

        return wrapper  # type: ignore[return-value]

    return decorator


def require_member(func: Callable[..., Any]) -> Callable[..., Any]:
    """Resolve ``member_id`` to a ``Member`` before the wrapped method runs.

    The public signature is ``method(self, member_id, ...)``; the wrapped
    implementation receives the loaded ``Member`` object instead of the ID.
    The decorated object must expose a ``members`` repository.
    Before any work is done it raises ``ValidationError`` for a malformed ID
    and ``MemberNotFoundError`` for an unknown one.
    """

    @functools.wraps(func)
    def wrapper(self: Any, member_id: str, *args: Any, **kwargs: Any) -> Any:
        member_id = validate_member_id(member_id)
        member = self.members.get_member(member_id)
        if member is None:
            raise MemberNotFoundError(member_id)
        return func(self, member, *args, **kwargs)

    return wrapper


def register_member_type(name: str) -> Callable[[C], C]:
    """Register a Member subclass under ``name`` so the factory can create it.

    Adding e.g. ``@register_member_type("faculty") class Faculty(Member)``
    is all it takes to support a new member type.
    """

    def decorator(cls: C) -> C:
        if name in MEMBER_REGISTRY:
            raise ValueError(f"Member type {name!r} is already registered")
        cls.member_type = name
        MEMBER_REGISTRY[name] = cls
        return cls

    return decorator
