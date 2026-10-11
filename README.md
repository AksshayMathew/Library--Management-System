# Library Management System

A small, testable library management system that focuses on OOP, SOLID design
principles and a layered architecture. The same service layer is exposed through
an **`argparse` CLI** and a **Flask REST API**, and data is stored in **SQLite**.

**Team:** Aksshay Mathew P · Ankit
**Employee ID used for personalisation:** `56040183`

| Personalised rule | Value |
|---|---|
| Genres | Fiction, History, Poetry, Science, Mystery, Technology |
| Student borrow limit | 3 |
| Staff borrow limit | 7 |
| Fine per day (overdue) | 1.73 |
| Loan period | 14 days |

## Architecture

```
 CLI (library/cli.py)        REST API (library/api/app.py)
            \                      /
             v                    v
      LibraryService (library/services/)  <- all business rules
             |                    \
             v                     v
  Domain models (library/models/)   FinePolicy
             |
             v
  Repository ABCs (library/storage/base.py)  <- the service depends on these
             |
             v
  SQLiteStorage (library/storage/sqlite_storage.py)
```

```
library/
  config.py            personalisation script + frozen Settings
  exceptions.py        LibraryError hierarchy
  validators.py        regex validation (ISBN-10/13 + checksum, email, IDs)
  decorators.py        @log_action, @require_member, @register_member_type
  logging_config.py    file logging -> logs/library.log
  models/              Book, Member (ABC) -> Student/Staff, Loan, Borrowable/Searchable
  storage/             repository ABCs + SQLite implementation
  services/            LibraryService, FinePolicy
  cli.py               argparse CLI
  api/app.py           Flask app factory
tests/                 pytest suite
scripts/seed_data.py   sample data
requests.http          ready-made API requests
docs/                  design note and curl examples
```

## Setup

Requires **Python 3.10+**.

**Windows (PowerShell)**

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Linux / macOS**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Optionally load sample data (one book per genre, two students, one staff member):

```bash
python scripts/seed_data.py
```

## Running the tests

```bash
python -m pytest -v
```

## Using the CLI

```bash
python -m library --help
python -m library show-config
python -m library add-book --isbn 0-306-40615-2 --title "Cosmos" --author "Carl Sagan" --genre Science --copies 2
python -m library add-member --member-id S010 --name "Meera Iyer" --email meera.iyer@example.com --type student
python -m library list-books --search sagan
python -m library list-books --genre Science
python -m library borrow --member-id S010 --isbn 0306406152
python -m library member-status --member-id S010
python -m library return --member-id S010 --isbn 0306406152
python -m library list-overdue
```

Global options (placed **before** the command):

| Option | Purpose |
|---|---|
| `--db PATH` | database file (default `library.db`, or `$LIBRARY_DB_PATH`) |
| `--employee-id ID` | personalise rules for another ID (default `$LIBRARY_EMPLOYEE_ID` or `56040183`) |
| `--today YYYY-MM-DD` | pretend it is another day, which is handy for showing overdue fines |

Demonstrating a fine (uses member `S001` from the seed data):

```bash
python -m library --today 2026-01-01 borrow --member-id S001 --isbn 9780062316097
python -m library --today 2026-01-20 list-overdue
python -m library --today 2026-01-20 return --member-id S001 --isbn 9780062316097   # 5 days late -> fine 8.65
```

Errors (unknown member, limit reached, invalid ISBN, unusable `--db` file...) are printed as
`Error: ...` with exit code 1. Every borrow and return is logged to `logs/library.log`.

Input rules worth knowing:
- ISBN-10s are converted to ISBN-13 (e.g. `0-13-235088-2` is stored as `9780132350884`), so either
  form finds the same book and it can't be added twice.
- `--copies` must be between 1 and 10,000. Genres must be one of the six shown by `show-config`.
- A return can't be dated before its borrow date, so a `--today` earlier than the loan is rejected.

## Using the REST API

```bash
python -m library.api          # serves http://127.0.0.1:5000
```

| Method | Endpoint | Success | Errors |
|---|---|---|---|
| GET | `/books?q=&genre=` | 200 | - |
| POST | `/books` | 201 | 400, 409 |
| POST | `/members` | 201 | 400, 409 |
| GET | `/members/<id>` | 200 | 404 |
| POST | `/borrow` | 201 | 400, 404, 409 |
| POST | `/return` | 200 (includes `fine`) | 400, 404 |

Example requests are in [`requests.http`](requests.http) and [`docs/api_examples.md`](docs/api_examples.md) (curl).

```bash
# member S001 and this ISBN come from the seed data
curl -X POST http://127.0.0.1:5000/borrow -H "Content-Type: application/json" \
     -d '{"member_id": "S001", "isbn": "9780132350884"}'
```
