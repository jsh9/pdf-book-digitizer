from __future__ import annotations

from types import SimpleNamespace

import pytest

from pdf_book_digitizer.text_fix import fix_ocr_text_with_LLM, has_only_whitespace_changes, strip_ansi_escape_codes


@pytest.mark.parametrize(
    ("before", "after", "expected"),
    [
        ("alpha\nbeta", "alpha beta", True),
        ("alpha\nbeta", "xalpha beta", False),
        ("alpha beta.", "alpha beta!", False),
    ],
)
def test_has_only_whitespace_changes(before: str, after: str, expected: bool) -> None:
    assert has_only_whitespace_changes(before, after) is expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("alpha\x1b[Kbeta", "alphabeta"),
        ("alpha\x1b[K\nbeta\x1b[K", "alpha\nbeta"),
        ("alpha\x1b[2Kbeta", "alphabeta"),
        ("alpha\x1b[31mbeta\x1b[0m", "alphabeta"),
        ("alpha\x1b[sbeta\x1b[u", "alphabeta"),
        ("alpha beta", "alpha beta"),
    ],
)
def test_strip_ansi_escape_codes(text: str, expected: str) -> None:
    assert strip_ansi_escape_codes(text) == expected


@pytest.mark.parametrize(
    ("responses", "expected"),
    [
        (["xalpha beta", "alpha beta"], "alpha beta"),
        (["alpha beta!", "xalpha beta", "alpha beta extra"], "alpha\nbeta"),
    ],
)
def test_fix_ocr_text_with_LLM_retries_invalid_visible_character_changes(
    monkeypatch,
    responses: list[str],
    expected: str,
) -> None:
    chat_responses = iter(
        SimpleNamespace(message=SimpleNamespace(content=response_text)) for response_text in responses
    )

    monkeypatch.setattr("pdf_book_digitizer.text_fix.chat", lambda **kwargs: next(chat_responses))

    assert fix_ocr_text_with_LLM("alpha\nbeta") == expected


@pytest.mark.parametrize(
    ("text", "response_text", "expected", "expected_fragment"),
    [
        ("alpha\x1b[K\nbeta", "alpha beta", "alpha beta", "alpha\nbeta"),
        ("alpha\x1b[31m\nbeta", "alpha beta", "alpha beta", "alpha\nbeta"),
        ("alpha\x1b[K", "xalpha", "alpha", "alpha"),
    ],
)
def test_fix_ocr_text_with_LLM_strips_ansi_escape_codes_before_prompt_and_fallback(
    monkeypatch,
    text: str,
    response_text: str,
    expected: str,
    expected_fragment: str,
) -> None:
    captured_prompt: dict[str, str] = {}

    def fake_chat(*, model, messages, think):
        captured_prompt["content"] = messages[0]["content"]
        return SimpleNamespace(message=SimpleNamespace(content=response_text))

    monkeypatch.setattr("pdf_book_digitizer.text_fix.chat", fake_chat)

    assert fix_ocr_text_with_LLM(text) == expected
    assert "\x1b[K" not in captured_prompt["content"]
    assert expected_fragment in captured_prompt["content"]
