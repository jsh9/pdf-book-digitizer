from __future__ import annotations

from pathlib import Path

from pdf_book_digitizer.assemble import read_page_markdown
from pdf_book_digitizer.models import PageContent
from pdf_book_digitizer.pipeline import run_ocr_from_images


def test_run_ocr_from_images_skips_initial_llm_fix_when_disabled(tmp_path: Path, monkeypatch) -> None:
    output_dir = tmp_path / "output"
    image_path = tmp_path / "page-0001.jpg"
    image_path.write_text("", encoding="utf-8")

    class FakeOCRClient:
        def __init__(self, model: str) -> None:
            self.model = model

        def ocr_page(self, page_image: Path, page_number: int, language_hint: str = "") -> PageContent:
            assert page_image == image_path
            assert page_number == 1
            assert language_hint == ""
            return PageContent(page_number=page_number, body_markdown="alpha\nbeta")

    monkeypatch.setattr("pdf_book_digitizer.pipeline.OllamaOCRClient", FakeOCRClient)

    fix_calls: list[tuple[str, str]] = []

    def fake_fix_ocr_text_with_LLM(text: str, model: str = "qwen3.5:27b") -> str:
        fix_calls.append((text, model))
        return "ALPHA BETA"

    monkeypatch.setattr("pdf_book_digitizer.pipeline.fix_ocr_text_with_LLM", fake_fix_ocr_text_with_LLM)
    monkeypatch.setattr("pdf_book_digitizer.pipeline.needs_hard_line_break_fix", lambda lines: False)

    run_ocr_from_images(
        image_paths=[image_path],
        output_dir=output_dir,
        model="glm-ocr",
        unwrap_text=False,
        llm_fix=False,
        llm_refix=False,
        preserve_input_names=False,
    )

    assert fix_calls == []
    raw_page = read_page_markdown(output_dir / "ocr" / "raw" / "page-0001.md", page_number=1)
    fixed_page = read_page_markdown(output_dir / "ocr" / "fixed" / "page-0001.md", page_number=1)
    assert raw_page.body_markdown == "alpha\nbeta"
    assert fixed_page.body_markdown == "alpha\nbeta"


def test_run_ocr_from_images_skips_refix_when_initial_llm_fix_is_disabled(tmp_path: Path, monkeypatch) -> None:
    output_dir = tmp_path / "output"
    image_path = tmp_path / "page-0001.jpg"
    image_path.write_text("", encoding="utf-8")

    class FakeOCRClient:
        def __init__(self, model: str) -> None:
            self.model = model

        def ocr_page(self, page_image: Path, page_number: int, language_hint: str = "") -> PageContent:
            return PageContent(page_number=page_number, body_markdown="alpha\nbeta")

    monkeypatch.setattr("pdf_book_digitizer.pipeline.OllamaOCRClient", FakeOCRClient)

    fix_calls: list[tuple[str, str]] = []

    def fake_fix_ocr_text_with_LLM(text: str, model: str = "qwen3.5:27b") -> str:
        fix_calls.append((text, model))
        return "ALPHA BETA"

    monkeypatch.setattr("pdf_book_digitizer.pipeline.fix_ocr_text_with_LLM", fake_fix_ocr_text_with_LLM)
    monkeypatch.setattr("pdf_book_digitizer.pipeline.needs_hard_line_break_fix", lambda lines: True)

    run_ocr_from_images(
        image_paths=[image_path],
        output_dir=output_dir,
        model="glm-ocr",
        unwrap_text=False,
        llm_fix=False,
        llm_refix=True,
        preserve_input_names=False,
    )

    assert fix_calls == []
    fixed_page = read_page_markdown(output_dir / "ocr" / "fixed" / "page-0001.md", page_number=1)
    assert fixed_page.body_markdown == "alpha\nbeta"
    assert (output_dir / "ocr" / "diff" / "page-0001.diff").exists()
    assert not (output_dir / "ocr" / "diff" / "page-0001-2.diff").exists()
