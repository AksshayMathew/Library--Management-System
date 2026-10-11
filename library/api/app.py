"""Flask REST API.

Route handlers only (1) read the HTTP request, (2) call the *same*
``LibraryService`` methods the CLI uses, and (3) turn the result into JSON.
No borrowing or fine logic lives here.
"""

from __future__ import annotations

from typing import Any

from flask import Flask, Response, jsonify, request
from werkzeug.exceptions import HTTPException

from library.exceptions import (
    BookNotAvailableError,
    BookNotFoundError,
    BorrowLimitExceededError,
    DuplicateBookError,
    DuplicateMemberError,
    LibraryError,
    LoanNotFoundError,
    MemberNotFoundError,
    StorageError,
    ValidationError,
)
from library.services.library_service import LibraryService


def create_app(service: LibraryService) -> Flask:
    """Application factory: build a Flask app around an already-wired service."""
    app = Flask(__name__)

    @app.get("/books")
    def list_books() -> tuple[Response, int]:
        """List the catalogue, optionally filtered with ?q=<text>&genre=<genre>."""
        books = service.search_books(query=request.args.get("q"), genre=request.args.get("genre"))
        return jsonify([book.to_dict() for book in books]), 200

    @app.post("/books")
    def add_book() -> tuple[Response, int]:
        """Add a book. Body: {isbn, title, author, genre, copies?}."""
        data = json_body()
        book = service.add_book(
            isbn=required(data, "isbn"),
            title=required(data, "title"),
            author=required(data, "author"),
            genre=required(data, "genre"),
            copies=data.get("copies", 1),
        )
        return jsonify(book.to_dict()), 201

    @app.post("/members")
    def add_member() -> tuple[Response, int]:
        """Register a member. Body: {member_id, name, email, member_type}."""
        data = json_body()
        member = service.add_member(
            member_id=required(data, "member_id"),
            name=required(data, "name"),
            email=required(data, "email"),
            member_type=required(data, "member_type"),
        )
        return jsonify(member.to_dict()), 201

    @app.get("/members/<member_id>")
    def get_member(member_id: str) -> tuple[Response, int]:
        """Member details, current loans and total fines."""
        return jsonify(service.member_status(member_id).to_dict()), 200

    @app.post("/borrow")
    def borrow() -> tuple[Response, int]:
        """Borrow a book. Body: {member_id, isbn}. Creates a loan -> 201."""
        data = json_body()
        loan = service.borrow_book(required(data, "member_id"), required(data, "isbn"))
        return jsonify(loan.to_dict()), 201

    @app.post("/return")
    def return_book() -> tuple[Response, int]:
        """Return a book. Body: {member_id, isbn}. Response includes the fine."""
        data = json_body()
        loan = service.return_book(required(data, "member_id"), required(data, "isbn"))
        return jsonify(loan.to_dict()), 200

    @app.errorhandler(LibraryError)
    def handle_library_error(exc: LibraryError) -> tuple[Response, int]:
        """Translate any domain error into a JSON body with the mapped HTTP status."""
        return jsonify(error=str(exc), type=type(exc).__name__), status_for(exc)

    @app.errorhandler(HTTPException)
    def handle_http_error(exc: HTTPException) -> tuple[Response, int]:
        """Unknown routes (404), wrong methods (405) etc. also answer in JSON."""
        return jsonify(error=exc.description, type=exc.name), exc.code or 500

    return app


# Single source of truth for how domain errors appear over HTTP.
ERROR_STATUS: dict[type[LibraryError], int] = {
    ValidationError: 400,
    BookNotFoundError: 404,
    MemberNotFoundError: 404,
    LoanNotFoundError: 404,
    DuplicateBookError: 409,
    DuplicateMemberError: 409,
    BookNotAvailableError: 409,
    BorrowLimitExceededError: 409,
    StorageError: 500,
}


def status_for(exc: LibraryError) -> int:
    """HTTP status for ``exc``, walking up its class hierarchy (unmapped errors -> 400)."""
    for cls in type(exc).__mro__:
        if cls in ERROR_STATUS:
            return ERROR_STATUS[cls]
    return 400


def json_body() -> dict[str, Any]:
    """Return the request's JSON object, or raise ``ValidationError`` if it is missing/malformed."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValidationError(
            "Request body must be a JSON object sent with the header 'Content-Type: application/json'"
        )
    return data


def required(data: dict[str, Any], field: str) -> Any:
    """Return ``data[field]``, raising ``ValidationError`` if the field is missing."""
    if field not in data or data[field] is None:
        raise ValidationError(f"Missing required field: '{field}'")
    return data[field]
