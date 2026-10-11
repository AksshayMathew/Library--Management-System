"""End-to-end tests for the argparse CLI against a temporary database file."""

from __future__ import annotations

import io
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from library.cli import main
from tests.conftest import CLEAN_CODE_ISBN

RunCli = Callable[..., int]


@pytest.fixture
def run_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> RunCli:
    """Run the CLI with an isolated database and log directory."""
    monkeypatch.chdir(tmp_path)
    db = str(tmp_path / "cli.db")

    def run(*args: str) -> int:
        return main(["--db", db, *args])

    return run


def test_full_borrow_return_flow(run_cli: RunCli, capsys: pytest.CaptureFixture[str]) -> None:
    assert run_cli("add-book", "--isbn", CLEAN_CODE_ISBN, "--title", "Clean Code",
                   "--author", "Robert C. Martin", "--genre", "Technology") == 0
    assert run_cli("add-member", "--member-id", "S1", "--name", "Asha",
                   "--email", "asha@example.com", "--type", "student") == 0
    assert run_cli("--today", "2026-01-01", "borrow", "--member-id", "S1", "--isbn", CLEAN_CODE_ISBN) == 0
    assert run_cli("--today", "2026-01-20", "list-overdue") == 0
    assert run_cli("--today", "2026-01-20", "return", "--member-id", "S1", "--isbn", CLEAN_CODE_ISBN) == 0

    out = capsys.readouterr().out
    assert "due 2026-01-15" in out
    assert "5 day(s) late" in out
    assert "fine due: 8.65" in out


def test_library_error_gives_exit_code_1(run_cli: RunCli, capsys: pytest.CaptureFixture[str]) -> None:
    assert run_cli("borrow", "--member-id", "NOPE", "--isbn", CLEAN_CODE_ISBN) == 1
    assert "No member found" in capsys.readouterr().err


def test_member_status_and_show_config(run_cli: RunCli, capsys: pytest.CaptureFixture[str]) -> None:
    run_cli("add-member", "--member-id", "T1", "--name", "Ravi", "--email", "ravi@example.com", "--type", "staff")
    assert run_cli("member-status", "--member-id", "T1") == 0
    assert run_cli("show-config") == 0
    out = capsys.readouterr().out
    assert "Books on loan: 0/7" in out
    assert "Fine per day:         1.73" in out


def test_unicode_title_does_not_crash_on_legacy_code_page(
    run_cli: RunCli, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Piped output on Windows uses cp1252, which cannot encode Devanagari."""
    raw = io.BytesIO()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(raw, encoding="cp1252"))
    assert run_cli("add-book", "--isbn", "9780140421996", "--title", "गीतांजलि",
                   "--author", "Rabindranath Tagore", "--genre", "Poetry") == 0
    assert run_cli("list-books") == 0
    sys.stdout.flush()
    assert b"Rabindranath Tagore" in raw.getvalue()


def test_unusable_database_path_gives_exit_code_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["--db", str(tmp_path / "missing" / "dir" / "x.db"), "list-books"]) == 1
    assert "Cannot open database" in capsys.readouterr().err


def test_return_before_borrow_date_is_rejected(run_cli: RunCli, capsys: pytest.CaptureFixture[str]) -> None:
    run_cli("add-book", "--isbn", CLEAN_CODE_ISBN, "--title", "Clean Code",
            "--author", "Robert C. Martin", "--genre", "Technology")
    run_cli("add-member", "--member-id", "S1", "--name", "Asha", "--email", "asha@example.com", "--type", "student")
    assert run_cli("--today", "2026-01-10", "borrow", "--member-id", "S1", "--isbn", CLEAN_CODE_ISBN) == 0
    assert run_cli("--today", "2026-01-05", "return", "--member-id", "S1", "--isbn", CLEAN_CODE_ISBN) == 1
    assert "before the borrow date" in capsys.readouterr().err


def test_logs_are_written_to_file(run_cli: RunCli, tmp_path: Path) -> None:
    run_cli("borrow", "--member-id", "NOPE", "--isbn", CLEAN_CODE_ISBN)
    assert "borrow FAILED" in (tmp_path / "logs" / "library.log").read_text(encoding="utf-8")
