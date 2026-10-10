"""Load sample books and members (one book per assigned genre) for demos.

Usage: ``python scripts/seed_data.py [--db library.db]`` (default: $LIBRARY_DB_PATH or library.db). Safe to run twice:
records that already exist are skipped.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from library.config import DB_PATH_ENV_VAR, DEFAULT_DB_PATH, load_settings  # noqa: E402
from library.exceptions import DuplicateBookError, DuplicateMemberError  # noqa: E402
from library.logging_config import configure_logging  # noqa: E402
from library.services.library_service import LibraryService  # noqa: E402
from library.storage.sqlite_storage import SQLiteStorage  # noqa: E402

BOOKS = [
    ("9780061120084", "To Kill a Mockingbird", "Harper Lee", "Fiction", 3),
    ("9780451524935", "Nineteen Eighty-Four", "George Orwell", "Fiction", 2),
    ("9780062316097", "Sapiens", "Yuval Noah Harari", "History", 2),
    ("9780140421996", "Leaves of Grass", "Walt Whitman", "Poetry", 1),
    ("9780553380163", "A Brief History of Time", "Stephen Hawking", "Science", 2),
    ("9780140437867", "The Hound of the Baskervilles", "Arthur Conan Doyle", "Mystery", 1),
    ("9780132350884", "Clean Code", "Robert C. Martin", "Technology", 4),
]

MEMBERS = [
    ("S001", "Asha Kumar", "asha.kumar@example.com", "student"),
    ("S002", "Rahul Menon", "rahul.menon@example.com", "student"),
    ("T001", "Dr. Priya Nair", "priya.nair@example.com", "staff"),
]


def seed(service: LibraryService) -> None:
    """Add every sample book and member, skipping ones already present."""
    for isbn, title, author, genre, copies in BOOKS:
        try:
            service.add_book(isbn, title, author, genre, copies)
            print(f"Added book:   {title}")
        except DuplicateBookError:
            print(f"Skipped book: {title} (already exists)")
    for member_id, name, email, member_type in MEMBERS:
        try:
            service.add_member(member_id, name, email, member_type)
            print(f"Added member:   {member_id} {name} ({member_type})")
        except DuplicateMemberError:
            print(f"Skipped member: {member_id} (already exists)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the library database with sample data")
    parser.add_argument("--db", default=os.environ.get(DB_PATH_ENV_VAR, DEFAULT_DB_PATH))
    args = parser.parse_args()
    configure_logging()
    with SQLiteStorage(args.db) as storage:
        seed(LibraryService.from_storage(storage, load_settings()))


if __name__ == "__main__":
    main()
