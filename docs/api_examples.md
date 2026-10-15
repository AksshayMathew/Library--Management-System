# API examples (curl)

Start the API first. It prints "Welcome to HCLTech Library Management System", asks for your
Employee ID (the rules for every request come from it), then listens on `http://127.0.0.1:5000`:

```bash
python -m library.api
```

The commands below use bash syntax (Git Bash, macOS, Linux). In **Windows
PowerShell**, call `curl.exe` (not the `curl` alias) and put the JSON body in a
file: `curl.exe -X POST http://127.0.0.1:5000/borrow -H "Content-Type: application/json" -d "@body.json"`.

| Method | Endpoint | Success | Errors |
|---|---|---|---|
| GET | `/books?q=&genre=` | 200 | - |
| POST | `/books` | 201 | 400 invalid/missing field, 409 duplicate ISBN |
| POST | `/members` | 201 | 400 invalid/missing field, 409 duplicate ID |
| GET | `/members/<id>` | 200 | 404 unknown member |
| POST | `/borrow` | 201 | 400 bad input, 404 unknown member/book, 409 limit reached or no copies |
| POST | `/return` | 200 (includes `fine`) | 400 bad input, 404 unknown member or no active loan |

Every error response has the shape `{"error": "<message>", "type": "<ErrorName>"}`.

## Catalogue

```bash
# List / search books -> 200
curl -i http://127.0.0.1:5000/books
curl -i "http://127.0.0.1:5000/books?q=clean&genre=Technology"

# Add a book -> 201
curl -i -X POST http://127.0.0.1:5000/books \
  -H "Content-Type: application/json" \
  -d '{"isbn": "978-0-13-235088-4", "title": "Clean Code", "author": "Robert C. Martin", "genre": "Technology", "copies": 2}'

# Same ISBN again -> 409
curl -i -X POST http://127.0.0.1:5000/books \
  -H "Content-Type: application/json" \
  -d '{"isbn": "9780132350884", "title": "Clean Code", "author": "Robert C. Martin", "genre": "Technology"}'

# Bad ISBN checksum -> 400
curl -i -X POST http://127.0.0.1:5000/books \
  -H "Content-Type: application/json" \
  -d '{"isbn": "978-0-13-235088-5", "title": "Broken", "author": "Nobody", "genre": "Fiction"}'
```

## Members

```bash
# Register a student -> 201
curl -i -X POST http://127.0.0.1:5000/members \
  -H "Content-Type: application/json" \
  -d '{"member_id": "S100", "name": "Asha Kumar", "email": "asha.kumar@example.com", "member_type": "student"}'

# Member details, loans and fines -> 200 (404 for an unknown ID)
curl -i http://127.0.0.1:5000/members/S100
```

## Borrowing and returning

```bash
# Borrow -> 201
curl -i -X POST http://127.0.0.1:5000/borrow \
  -H "Content-Type: application/json" \
  -d '{"member_id": "S100", "isbn": "9780132350884"}'

# Unknown member -> 404
curl -i -X POST http://127.0.0.1:5000/borrow \
  -H "Content-Type: application/json" \
  -d '{"member_id": "NOBODY", "isbn": "9780132350884"}'

# Return -> 200, body includes "fine"
curl -i -X POST http://127.0.0.1:5000/return \
  -H "Content-Type: application/json" \
  -d '{"member_id": "S100", "isbn": "9780132350884"}'
```

To demonstrate `409 BorrowLimitExceededError`, borrow with the same student
more times than the student limit (3); the next borrow returns 409.
