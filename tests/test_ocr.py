from __future__ import annotations

from pathlib import Path

from pdf_book_digitizer.ocr import DEESEEK_OCR_MODEL, DEESEEK_OCR_PROMPT, OllamaOCRClient


def test_ocr_client_uses_deepseek_markdown_prompt(tmp_path: Path, monkeypatch) -> None:
    image_path = tmp_path / "page-0001.jpg"
    image_path.write_text("", encoding="utf-8")
    calls: list[list[str]] = []

    class FakeCompletedProcess:
        def __init__(self) -> None:
            self.stdout = "## Title\n\nBody\n"

    def fake_subprocess_run(command: list[str], check: bool, capture_output: bool, text: bool) -> FakeCompletedProcess:
        calls.append(command)
        assert check is True
        assert capture_output is True
        assert text is True
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
