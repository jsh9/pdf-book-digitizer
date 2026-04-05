from __future__ import annotations

import pytest

from pdf_book_digitizer.hard_line_breaks import needs_hard_line_break_fix


@pytest.mark.parametrize(
    ("lines", "expected"),
    [
        (
            [
                "This line has almost exactly the same length as the rest.",
                "Another line with almost exactly the same text width too.",
                "Yet another line with almost exactly the same width too.",
                "One more line with almost exactly the same text width too.",
            ],
            True,
        ),
        (
            [
                "This line has almost exactly the same length as the rest.",
                "Another line with almost exactly the same text width too.",
                "Yet another line with almost exactly the same width too.",
                "One more line with almost exactly the same text width too.",
                "This line has almost exactly the same length as the rest.",
                "Yes?",
                "Another line with almost exactly the same text width too.",
                "Yet another line with almost exactly the same width too.",
                "One more line with almost exactly the same text width too.",
                "This line has almost exactly the same length as the rest.",
                "Another line with almost exactly the same text width too.",
                "Yet another line with almost exactly the same width too.",
                "OK",
                "One more line with almost exactly the same text width too.",
                "This line has almost exactly the same length as the rest.",
                "Another line with almost exactly the same text width too.",
                "Yet another line with almost exactly the same width too.",
                "One more line with almost exactly the same text width too.",
            ],
            True,
        ),
        (
            [
                "Short line.",
                "This is a much longer line than the first one by a wide margin.",
                "Medium sized line here.",
                "Tiny.",
            ],
            False,
        ),
        (
            [
                "",
                "Alpha beta gamma delta epsilon zeta eta theta iota kappa",
                "Alpha beta gamma delta epsilon zeta eta theta iota kappx",
                "Alpha beta gamma delta epsilon zeta eta theta iota kappz",
                "",
            ],
            True,
        ),
        (
            [
                "A heading",
                "",
                "A compact paragraph line.",
                "A much much much longer paragraph line than the others here.",
            ],
            False,
        ),
        (
            [
                "A centered heading of similar width",
                "Another centered heading line",
                "Third centered heading line",
            ],
            False,
        ),
        (
            [
                "字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字",
                "字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字",
                "字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字",
                "字字字字字字字字字字字字字字字字字字字字字字",
                "",
                "字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字",
                "字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字",
                "",
                "字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字",
                "字",
                "",
                "字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字",
                "字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字",
                "字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字",
                "字字字字字字字字字字字字字字字字字字字字字字字",
                "",
                "字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字",
                "字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字",
                "字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字",
                "字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字",
                "",
                "字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字",
                "字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字",
                "字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字",
                "字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字",
                "字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字",
                "字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字",
                "字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字",
                "字字字字字字字字字字字字字字字字字字字字字字字字",
            ],
            True,
        ),
        (
            [
                "字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字",
                "字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字",
                "字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字",
                "字字字字字字字字字字字字字字字",
                "",
                "字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字",
                "字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字",
                "字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字",
                "字字字字字字字字字字字字字字字字字字字字字字字字字字字",
            ],
            True,
        ),
    ],
)
def test_needs_hard_line_break_fix(lines: list[str], expected: bool) -> None:
    assert needs_hard_line_break_fix(lines) is expected
