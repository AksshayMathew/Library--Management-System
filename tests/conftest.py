"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta

import pytest

from library.config import Settings
from library.models.book import Book
from library.services.library_service import LibraryService
from library.storage.sqlite_storage import SQLiteStorage

CLEAN_CODE_ISBN = "9780132350884"


@pytest.fixture
def settings() -> Settings:
    """Settings derived from the team's employee ID (student=3, staff=7, fine=1.73)."""
    return Settings.from_employee_id("56040183")


@pytest.fixture
def storage() -> Iterator[SQLiteStorage]:
    """A fresh in-memory database for every test."""
    with SQLiteStorage(":memory:") as db:
        yield db


@pytest.fixture
def sample_book() -> Book:
    return Book(isbn=CLEAN_CODE_ISBN, title="Clean Code", author="Robert C. Martin", genre="Technology", total_copies=2)


class FakeClock:
    """A controllable replacement for ``date.today`` so tests can travel in time."""

    def __init__(self, today: date) -> None:
        self.today = today

    def __call__(self) -> date:
        return self.today

    def advance(self, days: int) -> None:
        self.today += timedelta(days=days)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(date(2026, 1, 1))


@pytest.fixture
def service(storage: SQLiteStorage, settings: Settings, clock: FakeClock) -> LibraryService:
    """A service with one Student (S1), one Staff member (T1) and a book with 10 copies."""
    svc = LibraryService.from_storage(storage, settings, today=clock)
    svc.add_member("S1", "Asha", "asha@example.com", "student")
    svc.add_member("T1", "Ravi", "ravi@example.com", "staff")
    svc.add_book(CLEAN_CODE_ISBN, "Clean Code", "Robert C. Martin", "Technology", copies=10)
    return svc
