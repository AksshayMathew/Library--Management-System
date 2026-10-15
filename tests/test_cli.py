"""End-to-end tests for the argparse CLI against a temporary database file."""

from __future__ import annotations

import io
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from library.cli import main
from library.config import Settings
from tests.conftest import CLEAN_CODE_ISBN

RunCli = Callable[..., int]
EMPLOYEE_ID = "56040183"


@pytest.fixture
def run_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> RunCli:
    """Run the CLI with an isolated database and log directory."""
    monkeypatch.chdir(tmp_path)
    db = str(tmp_path / "cli.db")

    def run(*args: str) -> int:
        return main(["--db", db, "--employee-id", EMPLOYEE_ID, *args])

    return run


def typed(*answers: str) -> Callable[[str], str]:
    """Fake keyboard: returns the given answers in order, then behaves like Ctrl+Z (EOF)."""
    remaining = list(answers)

    def read(prompt: str) -> str:
        print(prompt, end="")
        if not remaining:
            raise EOFError
        return remaining.pop(0)

    return read


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
    assert main(["--db", str(tmp_path / "missing" / "dir" / "x.db"), "--employee-id", EMPLOYEE_ID, "list-books"]) == 1
    assert "Cannot open database" in capsys.readouterr().err


def test_return_before_borrow_date_is_rejected(run_cli: RunCli, capsys: pytest.CaptureFixture[str]) -> None:
    run_cli("add-book", "--isbn", CLEAN_CODE_ISBN, "--title", "Clean Code",
            "--author", "Robert C. Martin", "--genre", "Technology")
    run_cli("add-member", "--member-id", "S1", "--name", "Asha", "--email", "asha@example.com", "--type", "student")
    assert run_cli("--today", "2026-01-10", "borrow", "--member-id", "S1", "--isbn", CLEAN_CODE_ISBN) == 0
    assert run_cli("--today", "2026-01-05", "return", "--member-id", "S1", "--isbn", CLEAN_CODE_ISBN) == 1
    assert "before the borrow date" in capsys.readouterr().err


# -- welcome message and Employee ID prompt -------------------------------------


def test_welcome_and_employee_id_prompt_for_one_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["--db", str(tmp_path / "x.db"), "show-config"], read=typed("56040183")) == 0
    out = capsys.readouterr().out
    assert out.startswith("Welcome to HCLTech Library Management System\n")
    assert "Please enter your Employee ID: " in out
    assert "Employee ID:          56040183" in out
    assert "Fine per day:         1.73" in out


def test_employee_id_decides_the_rules(run_cli: RunCli, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--db", str(tmp_path / "x.db"), "show-config"], read=typed(" 12345678 ")) == 0
    out = capsys.readouterr().out
    expected = Settings.from_employee_id("12345678")
    assert "Employee ID:          12345678" in out
    assert f"Student borrow limit: {expected.student_borrow_limit}" in out
    assert f"Fine per day:         {expected.fine_per_day:.2f}" in out


def test_invisible_characters_in_piped_input_are_ignored(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Windows PowerShell adds a byte-order mark when piping text into a program."""
    monkeypatch.chdir(tmp_path)
    assert main(["--db", str(tmp_path / "x.db")], read=typed("﻿56040183", "​show-config", "exit")) == 0
    out = capsys.readouterr().out
    assert "Library rules for Employee ID 56040183" in out
    assert "Fine per day:         1.73" in out


def test_invalid_employee_id_is_asked_again(tmp_path: Path, capsys: pytest.CaptureFixture[str],
                                            monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["--db", str(tmp_path / "x.db"), "show-config"], read=typed("", "56 04", "56040183")) == 0
    out = capsys.readouterr().out
    assert out.count("Please try again.") == 2
    assert "Employee ID:          56040183" in out


def test_three_invalid_employee_ids_give_exit_code_1(tmp_path: Path, capsys: pytest.CaptureFixture[str],
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["--db", str(tmp_path / "x.db"), "show-config"], read=typed("", "!!", "a b")) == 1
    assert "No valid Employee ID after 3 attempts" in capsys.readouterr().err


def test_no_employee_id_entered_gives_exit_code_1(tmp_path: Path, capsys: pytest.CaptureFixture[str],
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["--db", str(tmp_path / "x.db"), "show-config"], read=typed()) == 1
    assert "No Employee ID was entered" in capsys.readouterr().err


def test_interactive_session(tmp_path: Path, capsys: pytest.CaptureFixture[str],
                             monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    session = typed(
        "56040183",
        "add-member --member-id S1 --name \"Asha Kumar\" --email asha@example.com --type student",
        "member-status --member-id S1",
        "borrow --member-id NOPE --isbn 9780132350884",  # library error: session continues
        "fly-to-the-moon",  # unknown command: session continues
        "",
        "help",
        "exit",
    )
    assert main(["--db", str(tmp_path / "x.db")], read=session) == 0
    captured = capsys.readouterr()
    assert captured.out.startswith("Welcome to HCLTech Library Management System\n")
    assert "Library rules for Employee ID 56040183" in captured.out
    assert "Registered student S1: Asha Kumar <asha@example.com>" in captured.out
    assert "Books on loan: 0/3" in captured.out
    assert "Error: No member found with ID 'NOPE'" in captured.err
    assert "invalid choice: 'fly-to-the-moon'" in captured.err
    assert "show-config" in captured.out  # printed by 'help'
    assert captured.out.rstrip().endswith("Goodbye!")


def test_interactive_session_ends_on_eof(tmp_path: Path, capsys: pytest.CaptureFixture[str],
                                         monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["--db", str(tmp_path / "x.db")], read=typed("56040183", "show-config")) == 0
    out = capsys.readouterr().out
    assert "Staff borrow limit:   7" in out
    assert out.rstrip().endswith("Goodbye!")


def test_logs_are_written_to_file(run_cli: RunCli, tmp_path: Path) -> None:
    run_cli("borrow", "--member-id", "NOPE", "--isbn", CLEAN_CODE_ISBN)
    assert "borrow FAILED" in (tmp_path / "logs" / "library.log").read_text(encoding="utf-8")
