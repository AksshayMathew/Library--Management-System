"""Tests for the start-up interaction: welcome message and Employee ID prompt."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from library.cli import main
from library.config import Settings
from library.exceptions import ValidationError
from library.startup import EMPLOYEE_ID_PROMPT, WELCOME_MESSAGE, ask_employee_id, clean_input, describe_rules


def keyboard(*answers: str | BaseException) -> Callable[[str], str]:
    """Fake keyboard: returns each answer in turn; an exception instance is raised instead."""
    remaining = list(answers)

    def read(prompt: str) -> str:
        assert prompt == EMPLOYEE_ID_PROMPT
        answer = remaining.pop(0) if remaining else EOFError()
        if isinstance(answer, BaseException):
            raise answer
        return answer

    return read


def test_welcome_message_text() -> None:
    assert WELCOME_MESSAGE == "Welcome to HCLTech Library Management System"


def test_valid_id_is_returned_cleaned() -> None:
    assert ask_employee_id(keyboard("  56040183 "), write=print) == "56040183"


def test_invalid_answers_are_explained_and_asked_again() -> None:
    messages: list[str] = []
    assert ask_employee_id(keyboard("", "12 34", "56040183"), write=messages.append) == "56040183"
    assert len(messages) == 2
    assert all(m.endswith("Please try again.") for m in messages)


def test_gives_up_after_three_invalid_answers() -> None:
    with pytest.raises(ValidationError, match="after 3 attempts"):
        ask_employee_id(keyboard("!", "@", "#"), write=lambda _: None)


@pytest.mark.parametrize("interruption", [EOFError(), KeyboardInterrupt()])
def test_ctrl_z_or_ctrl_c_at_the_prompt_is_a_clean_error(interruption: BaseException) -> None:
    with pytest.raises(ValidationError, match="No Employee ID was entered"):
        ask_employee_id(keyboard(interruption), write=lambda _: None)


@pytest.mark.parametrize("command", [["show-config"], []])  # one command, and the interactive session
def test_ctrl_c_at_the_cli_prompt_exits_cleanly(
    command: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["--db", str(tmp_path / "x.db"), *command], read=keyboard(KeyboardInterrupt())) == 1
    assert "Error: No Employee ID was entered" in capsys.readouterr().err


@pytest.mark.parametrize("raw", ["﻿56040183", "​56040183​", " 56040183\r\n"])
def test_clean_input_removes_invisible_characters(raw: str) -> None:
    assert clean_input(raw) == "56040183"


def test_describe_rules_lists_the_personalised_values() -> None:
    text = describe_rules(Settings.from_employee_id("56040183"))
    assert "Employee ID 56040183" in text
    assert "Fiction, History, Poetry, Science, Mystery, Technology" in text
    assert "student 3, staff 7" in text
    assert "1.73 per day after 14 days" in text
