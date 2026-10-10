"""Flask REST API.

Route handlers only (1) read the HTTP request, (2) call the *same*
``LibraryService`` methods the CLI uses, and (3) turn the result into JSON.
No borrowing or fine logic lives here.
"""

from __future__ import annotations

from typing import Any

from flask import Flask, Response, jsonify, request

from library.exceptions import DuplicateBookError, ValidationError
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

    @app.errorhandler(ValidationError)
    def handle_validation_error(exc: ValidationError) -> tuple[Response, int]:
        return jsonify(error=str(exc)), 400

    @app.errorhandler(DuplicateBookError)
    def handle_duplicate(exc: DuplicateBookError) -> tuple[Response, int]:
        return jsonify(error=str(exc)), 409

    return app


def json_body() -> dict[str, Any]:
    """Return the request's JSON object, or raise ``ValidationError`` if it is missing/malformed."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValidationError("Request body must be a JSON object")
    return data


def required(data: dict[str, Any], field: str) -> Any:
    """Return ``data[field]``, raising ``ValidationError`` if the field is missing."""
    if field not in data or data[field] is None:
        raise ValidationError(f"Missing required field: '{field}'")
    return data[field]
