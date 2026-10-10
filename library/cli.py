"""Command-line interface built with ``argparse``.

This module only parses arguments, calls ``LibraryService`` and formats the
result for a terminal. It contains no business rules: every check (limits,
availability, validation) happens in the service, exactly as for the API.

Usage: ``python -m library <command> [options]`` - run with ``--help`` for details.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Sequence

from library.config import DB_PATH_ENV_VAR, DEFAULT_DB_PATH, load_settings
from library.exceptions import LibraryError
from library.logging_config import configure_logging
from library.models.book import Book
from library.services.library_service import LibraryService
from library.storage.sqlite_storage import SQLiteStorage

Handler = Callable[[LibraryService, argparse.Namespace], None]


# -- command handlers ----------------------------------------------------------


def cmd_add_book(service: LibraryService, args: argparse.Namespace) -> None:
    book = service.add_book(args.isbn, args.title, args.author, args.genre, args.copies)
    print(f"Added: {format_book(book)}")


def cmd_add_member(service: LibraryService, args: argparse.Namespace) -> None:
    member = service.add_member(args.member_id, args.name, args.email, args.type)
    print(f"Registered {member.member_type} {member.member_id}: {member.name} <{member.email}>")


def cmd_list_books(service: LibraryService, args: argparse.Namespace) -> None:
    found = False
    for book in service.search_books(query=args.search, genre=args.genre):
        print(format_book(book))
        found = True
    if not found:
        print("No books found.")


def cmd_borrow(service: LibraryService, args: argparse.Namespace) -> None:
    loan = service.borrow_book(args.member_id, args.isbn)
    print(f"{loan.member_id} borrowed {loan.isbn} (loan #{loan.loan_id}), due {loan.due_date.isoformat()}")


def cmd_return(service: LibraryService, args: argparse.Namespace) -> None:
    loan = service.return_book(args.member_id, args.isbn)
    fine = f"fine due: {loan.fine:.2f}" if loan.fine else "no fine"
    print(f"{loan.member_id} returned {loan.isbn} on {loan.returned_on.isoformat()} ({fine})")


def format_book(book: Book) -> str:
    """One-line, human-readable summary of a book."""
    return (
        f"{book.isbn} | {book.title} by {book.author} [{book.genre}] "
        f"- {book.available_copies}/{book.total_copies} available"
    )


# -- parser ---------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Create the top-level parser with one sub-parser per command."""
    parser = argparse.ArgumentParser(prog="library", description="Library Management System CLI")
    parser.add_argument(
        "--db",
        default=os.environ.get(DB_PATH_ENV_VAR, DEFAULT_DB_PATH),
        help=f"SQLite database file (default: ${DB_PATH_ENV_VAR} or {DEFAULT_DB_PATH})",
    )
    parser.add_argument("--employee-id", help="employee ID used to personalise the library rules")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    add_book = commands.add_parser("add-book", help="add a book to the catalogue")
    add_book.add_argument("--isbn", required=True, help="ISBN-10 or ISBN-13 (hyphens allowed)")
    add_book.add_argument("--title", required=True)
    add_book.add_argument("--author", required=True)
    add_book.add_argument("--genre", required=True, help="one of the genres shown by show-config")
    add_book.add_argument("--copies", type=int, default=1, help="number of copies (default: 1)")
    add_book.set_defaults(handler=cmd_add_book)

    add_member = commands.add_parser("add-member", help="register a new member")
    add_member.add_argument("--member-id", required=True)
    add_member.add_argument("--name", required=True)
    add_member.add_argument("--email", required=True)
    add_member.add_argument("--type", required=True, help="member type, e.g. student or staff")
    add_member.set_defaults(handler=cmd_add_member)

    list_books = commands.add_parser("list-books", help="list or search the catalogue")
    list_books.add_argument("--search", help="match title, author or ISBN")
    list_books.add_argument("--genre", help="filter by genre")
    list_books.set_defaults(handler=cmd_list_books)

    borrow = commands.add_parser("borrow", help="lend a book to a member")
    borrow.add_argument("--member-id", required=True)
    borrow.add_argument("--isbn", required=True)
    borrow.set_defaults(handler=cmd_borrow)

    return_ = commands.add_parser("return", help="return a borrowed book")
    return_.add_argument("--member-id", required=True)
    return_.add_argument("--isbn", required=True)
    return_.set_defaults(handler=cmd_return)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Returns the process exit code (0 = success, 1 = library error)."""
    args = build_parser().parse_args(argv)
    configure_logging()
    settings = load_settings(args.employee_id)
    handler: Handler = args.handler
    try:
        with SQLiteStorage(args.db) as storage:
            handler(LibraryService.from_storage(storage, settings), args)
    except LibraryError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
