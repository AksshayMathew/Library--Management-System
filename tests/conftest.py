"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from library.config import Settings
from library.models.book import Book
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
