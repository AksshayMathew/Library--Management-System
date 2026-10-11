"""Tests for the SQLite storage layer: CRUD, generators, transactions, persistence."""

from __future__ import annotations

import inspect
from datetime import date
from pathlib import Path

import pytest

from library.exceptions import StorageError
from library.models.book import Book
from library.models.loan import Loan
from library.models.member import Staff, Student
from library.storage.sqlite_storage import SQLiteStorage


def test_add_and_get_book(storage: SQLiteStorage, sample_book: Book) -> None:
    storage.add_book(sample_book)
    assert storage.get_book(sample_book.isbn) == sample_book
    assert storage.get_book("0306406152") is None


def test_iter_books_is_a_lazy_generator(storage: SQLiteStorage, sample_book: Book) -> None:
    storage.add_book(sample_book)
    books = storage.iter_books()
    assert inspect.isgenerator(books)
    assert [b.isbn for b in books] == [sample_book.isbn]


def test_members_round_trip_as_correct_subclass(storage: SQLiteStorage) -> None:
    storage.add_member(Student("S1", "Asha", "asha@example.com"))
    storage.add_member(Staff("T1", "Ravi", "ravi@example.com"))
    assert isinstance(storage.get_member("S1"), Student)
    assert isinstance(storage.get_member("T1"), Staff)
    assert storage.get_member("missing") is None


def test_loan_lifecycle(storage: SQLiteStorage, sample_book: Book) -> None:
    storage.add_book(sample_book)
    storage.add_member(Student("S1", "Asha", "asha@example.com"))
    loan = storage.add_loan(Loan(None, sample_book.isbn, "S1", date(2026, 1, 1), date(2026, 1, 15)))
    assert loan.loan_id is not None
    assert storage.count_active_loans("S1") == 1

    loan.returned_on = date(2026, 1, 10)
    storage.update_loan(loan)
    assert storage.count_active_loans("S1") == 0
    assert storage.get_active_loan("S1", sample_book.isbn) is None
    assert list(storage.iter_loans("S1", active_only=True)) == []
    assert [l.returned_on for l in storage.iter_loans("S1")] == [date(2026, 1, 10)]


def test_transaction_rolls_back_on_error(storage: SQLiteStorage, sample_book: Book) -> None:
    storage.add_book(sample_book)
    with pytest.raises(RuntimeError):
        with storage.transaction():
            sample_book.available_copies = 0
            storage.update_book(sample_book)  # nested write joins the outer transaction
            raise RuntimeError("simulated failure mid-operation")
    assert storage.get_book(sample_book.isbn).available_copies == 2


def test_transaction_commits_on_success(storage: SQLiteStorage, sample_book: Book) -> None:
    storage.add_book(sample_book)
    with storage.transaction():
        sample_book.available_copies = 1
        storage.update_book(sample_book)
    assert storage.get_book(sample_book.isbn).available_copies == 1


def test_missing_directory_raises_storage_error(tmp_path: Path) -> None:
    with pytest.raises(StorageError, match="Cannot open database"):
        SQLiteStorage(tmp_path / "no" / "such" / "folder" / "library.db")


def test_non_database_file_raises_storage_error(tmp_path: Path) -> None:
    not_a_db = tmp_path / "notes.txt"
    not_a_db.write_text("this is not a SQLite database\n" * 100, encoding="utf-8")
    with pytest.raises(StorageError, match="Cannot use database"):
        SQLiteStorage(not_a_db)


def test_sqlite_errors_become_storage_errors_and_roll_back(storage: SQLiteStorage, sample_book: Book) -> None:
    storage.add_book(sample_book)
    with pytest.raises(StorageError):
        with storage.transaction():
            sample_book.available_copies = 0
            storage.update_book(sample_book)
            storage.add_book(sample_book)  # same primary key -> sqlite3.IntegrityError
    assert storage.get_book(sample_book.isbn).available_copies == 2


def test_data_survives_restart(tmp_path: Path, sample_book: Book) -> None:
    db_file = tmp_path / "library.db"
    with SQLiteStorage(db_file) as first_run:
        first_run.add_book(sample_book)
        first_run.add_member(Staff("T1", "Ravi", "ravi@example.com"))

    with SQLiteStorage(db_file) as second_run:
        assert second_run.get_book(sample_book.isbn) == sample_book
        assert isinstance(second_run.get_member("T1"), Staff)
