from __future__ import annotations

import subprocess
from pathlib import Path

from pdf_book_digitizer.ocr import (
    DEESEEK_OCR_MODEL,
    DEESEEK_OCR_PROMPT,
    FREE_OCR_PROMPT,
    OCR_TIMEOUT_SECONDS,
    OCRTimeoutError,
    OllamaOCRClient,
)


def test_ocr_client_uses_deepseek_markdown_prompt(tmp_path: Path, monkeypatch) -> None:
    image_path = tmp_path / "page-0001.jpg"
    image_path.write_text("", encoding="utf-8")
    calls: list[list[str]] = []

    class FakeCompletedProcess:
        def __init__(self) -> None:
            self.stdout = "## Title\n\nBody\n"

    def fake_subprocess_run(
        command: list[str],
        check: bool,
        capture_output: bool,
        text: bool,
        timeout: int,
    ) -> FakeCompletedProcess:
        calls.append(command)
        assert check is True
        assert capture_output is True
        assert text is True
        assert timeout == OCR_TIMEOUT_SECONDS
        return FakeCompletedProcess()

    monkeypatch.setattr("pdf_book_digitizer.ocr.subprocess.run", fake_subprocess_run)

    page = OllamaOCRClient().ocr_page(image_path, page_number=7)

    assert page.page_number == 7
    assert page.body_markdown == "## Title\n\nBody"
    assert calls == [
        [
            "ollama",
            "run",
            DEESEEK_OCR_MODEL,
            f"{image_path.resolve()}\n{DEESEEK_OCR_PROMPT}",
        ]
    ]


def test_free_ocr_uses_free_ocr_prompt(tmp_path: Path, monkeypatch) -> None:
    image_path = tmp_path / "page-0001.jpg"
    image_path.write_text("", encoding="utf-8")
    calls: list[list[str]] = []

    class FakeCompletedProcess:
        def __init__(self) -> None:
            self.stdout = "① footnote text\n"

    def fake_subprocess_run(command, check, capture_output, text, timeout):
        calls.append(command)
        return FakeCompletedProcess()

    monkeypatch.setattr("pdf_book_digitizer.ocr.subprocess.run", fake_subprocess_run)

    free_ocr_text = OllamaOCRClient().free_ocr_page_text(image_path)

    assert free_ocr_text == "① footnote text"
    assert calls == [
        [
            "ollama",
            "run",
            DEESEEK_OCR_MODEL,
            f"{image_path.resolve()}\n{FREE_OCR_PROMPT}",
        ]
    ]


def test_ocr_client_raises_timeout_error_after_two_minutes(tmp_path: Path, monkeypatch) -> None:
    image_path = tmp_path / "page-0001.jpg"
    image_path.write_text("", encoding="utf-8")

    def fake_subprocess_run(command, check, capture_output, text, timeout):
        raise subprocess.TimeoutExpired(cmd=command, timeout=timeout)

    monkeypatch.setattr("pdf_book_digitizer.ocr.subprocess.run", fake_subprocess_run)

    try:
        OllamaOCRClient().ocr_page(image_path, page_number=1)
    except OCRTimeoutError as exc:
        assert str(OCR_TIMEOUT_SECONDS) in str(exc)
        assert str(image_path) in str(exc)
    else:
        raise AssertionError("Expected OCRTimeoutError")
