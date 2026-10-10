"""Tests for the Flask REST API using Flask's built-in test client."""

from __future__ import annotations

from typing import Any

import pytest
from flask.testing import FlaskClient

from library.api.app import create_app
from library.services.library_service import LibraryService
from tests.conftest import CLEAN_CODE_ISBN, FakeClock

POETRY_BOOK = {
    "isbn": "978-0-14-042199-6",
    "title": "Leaves of Grass",
    "author": "Walt Whitman",
    "genre": "Poetry",
    "copies": 1,
}


@pytest.fixture
def client(service: LibraryService) -> FlaskClient:
    """Test client around the seeded service (members S1/T1, Clean Code x10)."""
    return create_app(service).test_client()


def post(client: FlaskClient, url: str, body: Any) -> tuple[int, Any]:
    response = client.post(url, json=body)
    return response.status_code, response.get_json()


# -- /books -----------------------------------------------------------------------


def test_get_books_lists_catalogue(client: FlaskClient) -> None:
    response = client.get("/books")
    assert response.status_code == 200
    assert [b["isbn"] for b in response.get_json()] == [CLEAN_CODE_ISBN]


def test_get_books_with_search_and_genre(client: FlaskClient) -> None:
    post(client, "/books", POETRY_BOOK)
    assert [b["title"] for b in client.get("/books?q=whitman").get_json()] == ["Leaves of Grass"]
    assert [b["title"] for b in client.get("/books?genre=Technology").get_json()] == ["Clean Code"]
    assert client.get("/books?q=nothing-matches").get_json() == []


def test_post_book_created(client: FlaskClient) -> None:
    status, body = post(client, "/books", POETRY_BOOK)
    assert status == 201
    assert body["isbn"] == "9780140421996"  # normalised
    assert body["available_copies"] == 1


def test_post_book_duplicate_conflict(client: FlaskClient) -> None:
    post(client, "/books", POETRY_BOOK)
    status, body = post(client, "/books", POETRY_BOOK)
    assert status == 409
    assert body["type"] == "DuplicateBookError"


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({**POETRY_BOOK, "isbn": "978-0-14-042199-7"}, "Invalid ISBN"),
        ({k: v for k, v in POETRY_BOOK.items() if k != "title"}, "Missing required field: 'title'"),
        ({**POETRY_BOOK, "genre": "Fantasy"}, "not offered"),
        ({**POETRY_BOOK, "copies": 0}, "positive integer"),
        ([1, 2, 3], "JSON object"),
    ],
)
def test_post_book_bad_request(client: FlaskClient, body: Any, message: str) -> None:
    status, response = post(client, "/books", body)
    assert status == 400
    assert message in response["error"]


def test_malformed_json_is_400(client: FlaskClient) -> None:
    response = client.post("/books", data="{not json", content_type="application/json")
    assert response.status_code == 400


# -- /members ---------------------------------------------------------------------


def test_post_member_created_and_validated(client: FlaskClient) -> None:
    new_member = {"member_id": "S2", "name": "Meera", "email": "meera@example.com", "member_type": "student"}
    assert post(client, "/members", new_member)[0] == 201
    assert post(client, "/members", new_member)[0] == 409
    assert post(client, "/members", {**new_member, "member_id": "S3", "email": "nope"})[0] == 400
    assert post(client, "/members", {**new_member, "member_id": "S4", "member_type": "alien"})[0] == 400


def test_get_member_details_and_status(client: FlaskClient) -> None:
    post(client, "/borrow", {"member_id": "S1", "isbn": CLEAN_CODE_ISBN})
    response = client.get("/members/S1")
    body = response.get_json()
    assert response.status_code == 200
    assert body["member_type"] == "student"
    assert body["borrow_limit"] == 3
    assert body["active_loan_count"] == 1
    assert body["active_loans"][0]["isbn"] == CLEAN_CODE_ISBN


def test_get_unknown_member_404(client: FlaskClient) -> None:
    assert client.get("/members/NOPE").status_code == 404


# -- /borrow and /return ------------------------------------------------------------


def test_borrow_creates_loan(client: FlaskClient) -> None:
    status, body = post(client, "/borrow", {"member_id": "S1", "isbn": CLEAN_CODE_ISBN})
    assert status == 201
    assert body["loan_id"] == 1
    assert body["due_date"] == "2026-01-15"


def test_borrow_over_limit_conflict(client: FlaskClient) -> None:
    for _ in range(3):
        post(client, "/borrow", {"member_id": "S1", "isbn": CLEAN_CODE_ISBN})
    status, body = post(client, "/borrow", {"member_id": "S1", "isbn": CLEAN_CODE_ISBN})
    assert status == 409
    assert body["type"] == "BorrowLimitExceededError"


def test_borrow_unavailable_conflict(client: FlaskClient) -> None:
    post(client, "/books", POETRY_BOOK)
    post(client, "/borrow", {"member_id": "T1", "isbn": POETRY_BOOK["isbn"]})
    status, body = post(client, "/borrow", {"member_id": "S1", "isbn": POETRY_BOOK["isbn"]})
    assert status == 409
    assert body["type"] == "BookNotAvailableError"


@pytest.mark.parametrize(
    ("body", "expected_status"),
    [
        ({"member_id": "NOPE", "isbn": CLEAN_CODE_ISBN}, 404),  # unknown member
        ({"member_id": "S1", "isbn": "0306406152"}, 404),  # unknown book
        ({"member_id": "S1"}, 400),  # missing isbn
        ({"member_id": "S1", "isbn": "123"}, 400),  # malformed isbn
        ({"member_id": 123, "isbn": CLEAN_CODE_ISBN}, 400),  # member id not a string
    ],
)
def test_borrow_errors(client: FlaskClient, body: dict[str, str], expected_status: int) -> None:
    assert post(client, "/borrow", body)[0] == expected_status


def test_return_includes_fine(client: FlaskClient, clock: FakeClock) -> None:
    post(client, "/borrow", {"member_id": "S1", "isbn": CLEAN_CODE_ISBN})
    clock.advance(14 + 3)
    status, body = post(client, "/return", {"member_id": "S1", "isbn": CLEAN_CODE_ISBN})
    assert status == 200
    assert body["returned_on"] == "2026-01-18"
    assert body["fine"] == 5.19  # 3 days x 1.73


def test_return_without_loan_404(client: FlaskClient) -> None:
    status, body = post(client, "/return", {"member_id": "S1", "isbn": CLEAN_CODE_ISBN})
    assert status == 404
    assert body["type"] == "LoanNotFoundError"


def test_unknown_route_and_method_return_json(client: FlaskClient) -> None:
    assert client.get("/nowhere").get_json()["type"] == "Not Found"
    response = client.delete("/books")
    assert response.status_code == 405
    assert "error" in response.get_json()
