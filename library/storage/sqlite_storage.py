"""SQLite implementation of every storage interface, using the ``sqlite3`` module."""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from types import TracebackType

from library.exceptions import StorageError
from library.models.book import Book
from library.models.loan import Loan
from library.models.member import Member, create_member
from library.storage.base import LibraryStorage

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
    isbn             TEXT PRIMARY KEY,
    title            TEXT NOT NULL,
    author           TEXT NOT NULL,
    genre            TEXT NOT NULL,
    total_copies     INTEGER NOT NULL CHECK (total_copies > 0),
    available_copies INTEGER NOT NULL CHECK (available_copies >= 0)
);
CREATE TABLE IF NOT EXISTS members (
    member_id   TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    email       TEXT NOT NULL,
    member_type TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS loans (
    loan_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    isbn        TEXT NOT NULL REFERENCES books (isbn),
    member_id   TEXT NOT NULL REFERENCES members (member_id),
    borrowed_on TEXT NOT NULL,
    due_date    TEXT NOT NULL,
    returned_on TEXT,
    fine        REAL NOT NULL DEFAULT 0
);
"""


class SQLiteStorage(LibraryStorage):
    """Stores books, members and loans in a single SQLite database file.

    Usable as a context manager (``with SQLiteStorage(path) as storage:``)
    so the connection is always closed, even if an error occurs.
    """

    def __init__(self, db_path: str | Path = "library.db") -> None:
        """Open (or create) the database and its tables.

        Raises ``StorageError`` instead of a raw ``sqlite3`` error if the path
        cannot be opened (e.g. a missing folder) or the file is not a database.
        """
        self._transaction_depth = 0
        try:
            # check_same_thread=False lets the Flask dev server reuse the connection;
            # the API is run single-threaded so access is never concurrent.
            self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        except sqlite3.Error as exc:
            raise StorageError(f"Cannot open database {str(db_path)!r}: {exc}") from exc
        try:
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.executescript(SCHEMA)
        except sqlite3.Error as exc:
            self._conn.close()
            raise StorageError(f"Cannot use database {str(db_path)!r}: {exc}") from exc
        logger.debug("Opened SQLite database at %s", db_path)

    # -- connection lifecycle -------------------------------------------------

    def __enter__(self) -> SQLiteStorage:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying database connection."""
        self._conn.close()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Commit when the block succeeds, roll back if any exception escapes.

        Nested ``with storage.transaction():`` blocks join the outermost one,
        so a service operation that performs several writes (update the book,
        insert the loan) is saved all-or-nothing. Low-level ``sqlite3`` errors
        (constraint violations, a locked or read-only file...) are re-raised
        as ``StorageError`` so callers only ever see library exceptions.
        """
        self._transaction_depth += 1
        try:
            yield
            if self._transaction_depth == 1:
                self._conn.commit()
        except sqlite3.Error as exc:
            if self._transaction_depth == 1:
                self._conn.rollback()
                logger.error("Transaction rolled back after a database error: %s", exc)
            raise StorageError(f"Database error: {exc}") from exc
        except BaseException:
            if self._transaction_depth == 1:
                self._conn.rollback()
                logger.warning("Transaction rolled back")
            raise
        finally:
            self._transaction_depth -= 1

    # -- books ----------------------------------------------------------------

    def add_book(self, book: Book) -> None:
        with self.transaction():
            self._conn.execute(
                "INSERT INTO books (isbn, title, author, genre, total_copies, available_copies) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (book.isbn, book.title, book.author, book.genre, book.total_copies, book.available_copies),
            )

    def get_book(self, isbn: str) -> Book | None:
        row = self._conn.execute("SELECT * FROM books WHERE isbn = ?", (isbn,)).fetchone()
        return self._row_to_book(row) if row else None

    def update_book(self, book: Book) -> None:
        with self.transaction():
            self._conn.execute(
                "UPDATE books SET title = ?, author = ?, genre = ?, total_copies = ?, available_copies = ? "
                "WHERE isbn = ?",
                (book.title, book.author, book.genre, book.total_copies, book.available_copies, book.isbn),
            )

    def iter_books(self) -> Iterator[Book]:
        """Generator: yields one ``Book`` per row instead of loading the whole table."""
        cursor = self._conn.execute("SELECT * FROM books ORDER BY title")
        for row in cursor:
            yield self._row_to_book(row)

    # -- members --------------------------------------------------------------

    def add_member(self, member: Member) -> None:
        with self.transaction():
            self._conn.execute(
                "INSERT INTO members (member_id, name, email, member_type) VALUES (?, ?, ?, ?)",
                (member.member_id, member.name, member.email, member.member_type),
            )

    def get_member(self, member_id: str) -> Member | None:
        row = self._conn.execute("SELECT * FROM members WHERE member_id = ?", (member_id,)).fetchone()
        if row is None:
            return None
        return create_member(row["member_type"], row["member_id"], row["name"], row["email"])

    # -- loans ----------------------------------------------------------------

    def add_loan(self, loan: Loan) -> Loan:
        with self.transaction():
            cursor = self._conn.execute(
                "INSERT INTO loans (isbn, member_id, borrowed_on, due_date, returned_on, fine) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    loan.isbn,
                    loan.member_id,
                    loan.borrowed_on.isoformat(),
                    loan.due_date.isoformat(),
                    loan.returned_on.isoformat() if loan.returned_on else None,
                    loan.fine,
                ),
            )
        loan.loan_id = cursor.lastrowid
        return loan

    def get_active_loan(self, member_id: str, isbn: str) -> Loan | None:
        row = self._conn.execute(
            "SELECT * FROM loans WHERE member_id = ? AND isbn = ? AND returned_on IS NULL "
            "ORDER BY loan_id LIMIT 1",
            (member_id, isbn),
        ).fetchone()
        return self._row_to_loan(row) if row else None

    def update_loan(self, loan: Loan) -> None:
        with self.transaction():
            self._conn.execute(
                "UPDATE loans SET returned_on = ?, fine = ? WHERE loan_id = ?",
                (loan.returned_on.isoformat() if loan.returned_on else None, loan.fine, loan.loan_id),
            )

    def count_active_loans(self, member_id: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) FROM loans WHERE member_id = ? AND returned_on IS NULL", (member_id,)
        ).fetchone()
        return int(row[0])

    def iter_loans(self, member_id: str | None = None, active_only: bool = False) -> Iterator[Loan]:
        """Generator: yields loans one row at a time, optionally filtered."""
        query = "SELECT * FROM loans WHERE 1 = 1"
        params: list[str] = []
        if member_id is not None:
            query += " AND member_id = ?"
            params.append(member_id)
        if active_only:
            query += " AND returned_on IS NULL"
        for row in self._conn.execute(query + " ORDER BY due_date, loan_id", params):
            yield self._row_to_loan(row)

    # -- row mapping ----------------------------------------------------------

    @staticmethod
    def _row_to_book(row: sqlite3.Row) -> Book:
        return Book(
            isbn=row["isbn"],
            title=row["title"],
            author=row["author"],
            genre=row["genre"],
            total_copies=row["total_copies"],
            available_copies=row["available_copies"],
        )

    @staticmethod
    def _row_to_loan(row: sqlite3.Row) -> Loan:
        return Loan(
            loan_id=row["loan_id"],
            isbn=row["isbn"],
            member_id=row["member_id"],
            borrowed_on=date.fromisoformat(row["borrowed_on"]),
            due_date=date.fromisoformat(row["due_date"]),
            returned_on=date.fromisoformat(row["returned_on"]) if row["returned_on"] else None,
            fine=row["fine"],
        )
