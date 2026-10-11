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
(`api/app.py:74`) both call the same `LibraryService.borrow_book` (`library/services/library_service.py:170`).
Returning works the same way (`cli.py:56`, `app.py:81` → `library_service.py:196`). As a result, the CLI and
the API cannot disagree about a borrow limit or a fine.

The **service layer** (`library/services/`) is where all the rules live: borrow limits, availability, genres,
due dates and fines. The **domain layer** (`library/models/`) holds `Book`, the `Member` hierarchy and `Loan`.
The **storage layer** (`library/storage/`) defines abstract repositories and implements them with SQLite.

Errors flow upward as custom exceptions that all derive from `LibraryError` (`library/exceptions.py:13`).
They describe *what* went wrong, never how to show it. Each delivery layer decides how to present them.
The CLI prints `Error: ...` and exits with code 1 (`cli.py:172`). The API maps each exception class to an
HTTP status in a single table (`app.py:98`): 400 for validation, 404 for not found, 409 for rule violations
and 500 for database failures. Even a raw `sqlite3` error never escapes: storage re-raises it as
`StorageError`.
The input regexes live only in `library/validators.py`, and the service calls them, so both front-ends
reject exactly the same input (DRY).

Each advanced feature is used for a real purpose:
- **Decorators:** `log_action` logs every borrow and return (`library/decorators.py:27`). `require_member`
  fails fast when the member doesn't exist (`decorators.py:52`). `register_member_type` is a class
  decorator for new member types (`decorators.py:73`).
- **Generators:** `iter_books` and `iter_loans` stream rows from the database cursor (`sqlite_storage.py:144`,
  `:205`). `search_books` and `iter_overdue_loans` (`library_service.py:141`, `:217`) filter those streams
  without ever building a full list.
- **Context managers:** `SQLiteStorage.transaction()` (`sqlite_storage.py:95`) commits on success and rolls
  back on any exception, so a failed borrow never leaves a book marked as lent with no loan record.
  `SQLiteStorage` itself is a context manager that always closes the connection.

## 2. SOLID walkthrough

**Single Responsibility.** `Book` (`library/models/book.py:13`) holds its own data and copy-count behaviour
(`checkout`, `checkin`, `matches`) and nothing else. It doesn't validate ISBNs (`validators.py`) or save
itself (`sqlite_storage.py`). Fine arithmetic has its own class, `FinePolicy`
(`library/services/fine_policy.py:12`), and logging setup is in `logging_config.py`. `LibraryService`
coordinates a use case but hands each rule to the class that owns it.

**Open/Closed.** Member types register themselves with `@register_member_type("...")`
(`decorators.py:73`, used at `member.py:51` and `:59`). The factory `create_member` (`member.py:67`) looks the
type up in `MEMBER_REGISTRY` (`decorators.py:24`). Adding a `Faculty` type therefore means *adding one class*,
without editing `Student`, `Staff`, the factory or the service. The test
`test_new_member_type_works_without_changing_service` does exactly this. `FinePolicy` is a second extension
point: a capped or grace-period policy can be passed to `LibraryService(fine_policy=...)`.

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

`get_my_library_parameters("56040183")` (`library/config.py:22`) produces our rules. We wrap them in a frozen
`Settings` dataclass (`config.py:37`) so no layer can change a limit at runtime.

| Parameter | Value | Where it is enforced |
|---|---|---|
| genres | Fiction, History, Poetry, Science, Mystery, Technology | `_validate_genre` (`library_service.py:253`), so other genres are rejected with 400 |
| student_borrow_limit | 3 | `Student.borrow_limit` (`member.py:55`) |
| staff_borrow_limit | 7 | `Staff.borrow_limit` (`member.py:63`) |
| fine_per_day | 1.73 | `FinePolicy.calculate` (`fine_policy.py:36`): days late × 1.73, rounded to 2 dp |
| loan period (our choice) | 14 days | `Settings.loan_period_days` |

The ID can be overridden with `--employee-id` or the `LIBRARY_EMPLOYEE_ID` variable (`config.py:64`).

## 4. Trade-offs we made consciously

- **SQLite instead of JSON.** SQLite gives us real transactions, so a borrow's two writes are
  all-or-nothing. It also lets us run queries like "active loans for member X" without loading
  everything, and its cursor feeds our generators naturally. The cost is a schema to maintain and data that
  is less human-readable than a JSON file.
- **Flask instead of FastAPI.** The brief asks for **400** on invalid bodies, but FastAPI returns 422 by
  default and would validate through a second schema layer (Pydantic). Flask's small `json_body()` and
  `required()` helpers (`app.py:119`, `:129`) let every endpoint reuse *our* validators. We gave up
  automatic OpenAPI docs in exchange.
- **A known ISP/SRP compromise.** `SQLiteStorage` (`sqlite_storage.py:48`) implements all four storage
  interfaces in one class. This is pragmatic: there is one connection and one transaction scope. But the
  class will grow with every new table. The refactor would be to split it into `SQLiteBookRepository`,
  `SQLiteMemberRepository` and `SQLiteLoanRepository` sharing a connection/unit-of-work object. The service
  would not change, because it already takes the repositories separately.
- **`require_member` swaps the argument.** Callers pass a `member_id`, but the method body receives the
  loaded `Member` (`decorators.py:52`). This avoids looking the member up twice, at the cost of a less
  obvious signature, so we documented it in the docstrings.
- **Single-threaded API.** One SQLite connection is shared, so the development server runs with
  `threaded=False` (`library/api/__main__.py:19`). A production version would open a connection per
  request.
- **Fines are calculated, not paid.** `total_fines` adds up the fines recorded at return plus the fines still
  accruing on overdue books. A payments feature was out of scope (KISS).
