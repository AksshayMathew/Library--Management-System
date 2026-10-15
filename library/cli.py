"""Command-line interface built with ``argparse``.

This module only parses arguments, calls ``LibraryService`` and formats the
result for a terminal. It contains no business rules: every check (limits,
availability, validation) happens in the service, exactly as for the API.

Usage:
  ``python -m library``                     interactive session: welcome, Employee ID, then commands
  ``python -m library <command> [options]`` one command (asks for the Employee ID unless
                                            ``--employee-id`` is given) - run ``--help`` for details.
"""

from __future__ import annotations

import argparse
import io
import os
import shlex
import sys
from collections.abc import Callable, Sequence
from datetime import date

from library.config import DB_PATH_ENV_VAR, DEFAULT_DB_PATH, Settings, load_settings
from library.exceptions import LibraryError
from library.logging_config import configure_logging
from library.models.book import Book
from library.services.library_service import LibraryService
from library.startup import WELCOME_MESSAGE, Reader, ask_employee_id, clean_input, describe_rules
from library.storage.sqlite_storage import SQLiteStorage

EXIT_WORDS = {"exit", "quit"}
HELP_WORDS = {"help", "?"}

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


def cmd_list_overdue(service: LibraryService, args: argparse.Namespace) -> None:
    found = False
    for overdue in service.iter_overdue_loans():
        loan = overdue.loan
        print(
            f"{loan.member_id} | {loan.isbn} | due {loan.due_date.isoformat()} | "
            f"{overdue.days_overdue} day(s) late | fine so far: {overdue.accrued_fine:.2f}"
        )
        found = True
    if not found:
        print("No overdue loans.")


def cmd_member_status(service: LibraryService, args: argparse.Namespace) -> None:
    status = service.member_status(args.member_id)
    member = status.member
    print(f"{member.member_id}: {member.name} <{member.email}> ({member.member_type})")
    print(f"Books on loan: {len(status.active_loans)}/{status.borrow_limit}")
    for loan in status.active_loans:
        print(f"  - {loan.isbn}, borrowed {loan.borrowed_on.isoformat()}, due {loan.due_date.isoformat()}")
    print(f"Total fines: {status.total_fines:.2f}")


def cmd_show_config(service: LibraryService, args: argparse.Namespace) -> None:
    settings = service.settings
    print(f"Employee ID:          {settings.employee_id}")
    print(f"Genres:               {', '.join(settings.genres)}")
    print(f"Student borrow limit: {settings.student_borrow_limit}")
    print(f"Staff borrow limit:   {settings.staff_borrow_limit}")
    print(f"Fine per day:         {settings.fine_per_day:.2f}")
    print(f"Loan period (days):   {settings.loan_period_days}")


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
    parser.add_argument(
        "--employee-id",
        help="your Employee ID (if omitted, you are asked for it when the program starts)",
    )
    parser.add_argument(
        "--today",
        type=parse_date,
        help="pretend today is YYYY-MM-DD (useful to demonstrate overdue fines)",
    )
    commands = parser.add_subparsers(dest="command", metavar="COMMAND")

    add_book = commands.add_parser("add-book", help="add a book to the catalogue")
    add_book.add_argument("--isbn", required=True, help="ISBN-10 or ISBN-13, hyphens allowed (stored as ISBN-13)")
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

    list_overdue = commands.add_parser("list-overdue", help="list unreturned books past their due date")
    list_overdue.set_defaults(handler=cmd_list_overdue)

    member_status = commands.add_parser("member-status", help="show a member's loans and fines")
    member_status.add_argument("--member-id", required=True)
    member_status.set_defaults(handler=cmd_member_status)

    show_config = commands.add_parser("show-config", help="show the personalised library rules")
    show_config.set_defaults(handler=cmd_show_config)

    return parser


def parse_date(raw: str) -> date:
    """argparse type for ``YYYY-MM-DD`` dates."""
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid date {raw!r}, expected YYYY-MM-DD") from None


def use_safe_console_output() -> None:
    """Never crash on characters the output encoding cannot represent.

    When output is piped or redirected on Windows, Python encodes it with the
    legacy code page (e.g. cp1252), which cannot represent a Hindi or Chinese
    book title. Such characters are shown as '?' instead of raising
    ``UnicodeEncodeError`` - which would otherwise happen *after* the change
    was already saved.
    """
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(errors="replace")


def run_command(storage: SQLiteStorage, settings: Settings, args: argparse.Namespace) -> None:
    """Run one parsed command against the open database."""
    today: Callable[[], date] = (lambda: args.today) if args.today else date.today
    handler: Handler = args.handler
    handler(LibraryService.from_storage(storage, settings, today=today), args)


def run_interactive(
    parser: argparse.ArgumentParser, storage: SQLiteStorage, settings: Settings, read: Reader
) -> int:
    """Read commands one line at a time until the user types ``exit``.

    Each line uses the same syntax as a one-off command, without ``python -m library``
    in front, e.g. ``borrow --member-id S001 --isbn 9780132350884``. The Employee ID
    entered at start-up applies to the whole session.
    """
    print(describe_rules(settings))
    print("Type a command, e.g. 'list-books' or 'borrow --member-id S001 --isbn 9780132350884'.")
    print("Type 'help' to see every command, or 'exit' to quit.")
    while True:
        try:
            line = clean_input(read("library> "))
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line.lower() in EXIT_WORDS:
            break
        if line.lower() in HELP_WORDS:
            parser.print_help()
            continue
        try:
            line_args = parser.parse_args(shlex.split(line))
        except ValueError as exc:  # e.g. an unclosed quote
            print(f"Error: {exc}", file=sys.stderr)
            continue
        except SystemExit:  # argparse already printed the usage error (or --help)
            continue
        if line_args.command is None:
            print("Please type a command, e.g. 'list-books'. Type 'help' to see them all.")
            continue
        if line_args.employee_id not in (None, settings.employee_id):
            print(f"Note: this session uses Employee ID {settings.employee_id}. "
                  "Exit and start again to use a different one.")
        try:
            run_command(storage, settings, line_args)
        except LibraryError as exc:
            print(f"Error: {exc}", file=sys.stderr)
    print("Goodbye!")
    return 0


def main(argv: Sequence[str] | None = None, read: Reader = input) -> int:
    """Entry point. Returns the process exit code (0 = success, 1 = library error).

    Without ``--employee-id`` the user is welcomed and asked for their Employee ID.
    Without a command, an interactive session starts.
    """
    use_safe_console_output()
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging()
    interactive = args.command is None
    try:
        if interactive or args.employee_id is None:
            print(WELCOME_MESSAGE)
        employee_id = args.employee_id if args.employee_id is not None else ask_employee_id(read)
        settings = load_settings(employee_id)
        with SQLiteStorage(args.db) as storage:
            if interactive:
                return run_interactive(parser, storage, settings, read)
            run_command(storage, settings, args)
    except LibraryError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
