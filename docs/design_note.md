# Design Note: Library Management System

**Team:** Aksshay Mathew P · Ankit  **Employee ID used for personalisation:** 56040183

## 1. Architecture

```
 CLI (argparse)            REST API (Flask)          <- delivery: parse input, format output
        \                      /
         v                    v
        LibraryService + FinePolicy                  <- business rules (the only place)
         |                    |
         v                    v
   Domain models          Repository ABCs            <- Book, Member/Student/Staff, Loan
                              |
                              v
                        SQLiteStorage                <- persistence (sqlite3)
```

The system has four layers, and each one only talks to the layer below it.
The **delivery layer** has two front-ends: an `argparse` CLI (`library/cli.py`) and a Flask API
(`library/api/app.py`). Both parse their input, call the service, and format the result as text or JSON.
They contain no library rules. For example, borrowing from the terminal (`cli.py:51`) and borrowing over HTTP
(`api/app.py:73`) both call the same `LibraryService.borrow_book` (`library/services/library_service.py:170`).
Returning works the same way (`cli.py:56`, `app.py:80` → `library_service.py:196`). As a result, the CLI and
the API cannot disagree about a borrow limit or a fine.

The **service layer** (`library/services/`) is where all the rules live: borrow limits, availability, genres,
due dates and fines. The **domain layer** (`library/models/`) holds `Book`, the `Member` hierarchy and `Loan`.
The **storage layer** (`library/storage/`) defines abstract repositories and implements them with SQLite.

Errors flow upward as custom exceptions that all derive from `LibraryError` (`library/exceptions.py:13`).
They describe *what* went wrong, never how to show it. Each delivery layer decides how to present them.
The CLI prints `Error: ...` and exits with code 1 (`cli.py:172`). The API maps each exception class to an
HTTP status in a single table (`app.py:97`): 400 for validation, 404 for not found, 409 for rule violations.
The input regexes live only in `library/validators.py`, and the service calls them, so both front-ends
reject exactly the same input (DRY).

Each advanced feature is used for a real purpose:
- **Decorators:** `log_action` logs every borrow and return (`library/decorators.py:27`). `require_member`
  fails fast when the member doesn't exist (`decorators.py:52`). `register_member_type` is a class
  decorator for new member types (`decorators.py:73`).
- **Generators:** `iter_books` and `iter_loans` stream rows from the database cursor (`sqlite_storage.py:125`,
  `:186`). `search_books` and `iter_overdue_loans` (`library_service.py:141`, `:217`) filter those streams
  without ever building a full list.
- **Context managers:** `SQLiteStorage.transaction()` (`sqlite_storage.py:82`) commits on success and rolls
  back on any exception, so a failed borrow never leaves a book marked as lent with no loan record.
  `SQLiteStorage` itself is a context manager that always closes the connection.

## 2. SOLID walkthrough

**Single Responsibility.** _To be written._

**Open/Closed.** _To be written._

**Liskov Substitution.** `Member` (`member.py:15`) sets the contract: `borrow_limit(settings)` and
`can_borrow(active_loans, settings)`. `Student` (`member.py:52`) and `Staff` (`member.py:60`) only change the
limit's *value*. They don't add preconditions or raise new exceptions. `borrow_book` never checks the
concrete type (no `isinstance`), so any subclass works there, including the test-only `Faculty`.

**Interface Segregation.** Capabilities are small, separate ABCs: `Borrowable` (`interfaces.py:14`) and
`Searchable` (`interfaces.py:30`). A reference-only item could be searchable without being forced to
implement `checkout`. Storage is split the same way into `BookRepository`, `MemberRepository`,
`LoanRepository` and `TransactionManager` (`storage/base.py:19`, `:39`, `:51`, `:75`) rather than one large
"Database" interface. The service receives each one separately (`library_service.py:88`).

**Dependency Inversion.** `LibraryService.__init__` (`library_service.py:88`) is typed against those
abstractions plus a `FinePolicy` and a `today()` clock. It never imports `sqlite3`. The concrete
`SQLiteStorage` is chosen only at the outer edges: `cli.py:172` and `library/api/__main__.py`. This is what
makes the code testable. The tests inject an in-memory database and a `FakeClock` (`tests/conftest.py`)
to check fines on exact dates, and a JSON back-end could replace SQLite without changing the service.

## 3. Personalised parameters

_To be written._

## 4. Trade-offs we made consciously

_To be written._
