from __future__ import annotations

from pathlib import Path

from pdf_book_digitizer.assemble import read_page_markdown
from pdf_book_digitizer.cli import digitize_book, run_ocr_from_images
from pdf_book_digitizer.models import PageContent
from pdf_book_digitizer.ocr import OCRTimeoutError


def test_run_ocr_from_images_writes_raw_markdown_output(tmp_path: Path, monkeypatch) -> None:
    output_dir = tmp_path / "output"
    image_path = tmp_path / "page-0001.jpg"
    image_path.write_text("", encoding="utf-8")

    class FakeOCRClient:
        def ocr_page(self, page_image: Path, page_number: int) -> PageContent:
            assert page_image == image_path
            assert page_number == 1
            return PageContent(page_number=page_number, body_markdown="# Page 1\n\nalpha")

    monkeypatch.setattr("pdf_book_digitizer.cli.OllamaOCRClient", FakeOCRClient)

    run_ocr_from_images(
        image_paths=[image_path],
        output_dir=output_dir,
        preserve_input_names=False,
    )

    raw_page = read_page_markdown(output_dir / "ocr" / "raw" / "page-0001.md", page_number=1)
    assert raw_page.body_markdown == "# Page 1\n\nalpha"


def test_run_ocr_from_images_skips_existing_raw_markdown(tmp_path: Path, monkeypatch, capsys) -> None:
    output_dir = tmp_path / "output"
    image_path = tmp_path / "001-cover.jpg"
    image_path.write_text("", encoding="utf-8")

    raw_output = output_dir / "ocr" / "raw" / "001-cover.md"
    raw_output.parent.mkdir(parents=True, exist_ok=True)
    raw_output.write_text("existing markdown\n", encoding="utf-8")

    class FakeOCRClient:
        def __init__(self) -> None:
            raise AssertionError("OCR client should not be constructed when all pages are already resumable")

    monkeypatch.setattr("pdf_book_digitizer.cli.OllamaOCRClient", FakeOCRClient)

    run_ocr_from_images(
        image_paths=[image_path],
        output_dir=output_dir,
        preserve_input_names=True,
    )

    assert raw_output.read_text(encoding="utf-8") == "existing markdown\n"
    assert "Skipping 001-cover; found existing raw output" in capsys.readouterr().out


def test_run_ocr_from_images_writes_empty_markdown_after_timeout(tmp_path: Path, monkeypatch, capsys) -> None:
    output_dir = tmp_path / "output"
    image_path = tmp_path / "page-0001.jpg"
    image_path.write_text("", encoding="utf-8")

    class FakeOCRClient:
        def ocr_page(self, page_image: Path, page_number: int) -> PageContent:
            raise OCRTimeoutError("timed out")

    monkeypatch.setattr("pdf_book_digitizer.cli.OllamaOCRClient", FakeOCRClient)

    run_ocr_from_images(
        image_paths=[image_path],
        output_dir=output_dir,
        preserve_input_names=False,
    )

    raw_output = output_dir / "ocr" / "raw" / "page-0001.md"
    assert raw_output.exists()
    assert raw_output.read_text(encoding="utf-8") == "\n"
    assert "Skipping page-0001; OCR exceeded 120 seconds" in capsys.readouterr().out


def test_digitize_book_renders_pdf_pages_before_ocr(tmp_path: Path, monkeypatch) -> None:
    input_pdf = tmp_path / "book.pdf"
    input_pdf.write_text("", encoding="utf-8")
    output_dir = tmp_path / "output"
    rendered_paths = [tmp_path / "rendered" / "page-0001.jpg"]
    calls: list[tuple[str, object]] = []

    def fake_render_pdf_to_jpgs(input_path: Path, pages_dir: Path, dpi: int) -> list[Path]:
        calls.append(("render", input_path, pages_dir, dpi))
        return rendered_paths

    def fake_run_ocr_from_images(image_paths: list[Path], output_dir: Path, preserve_input_names: bool = True) -> None:
        calls.append(("ocr", image_paths, output_dir, preserve_input_names))

    monkeypatch.setattr("pdf_book_digitizer.cli.render_pdf_to_jpgs", fake_render_pdf_to_jpgs)
    monkeypatch.setattr("pdf_book_digitizer.cli.run_ocr_from_images", fake_run_ocr_from_images)

    digitize_book(
        input_pdf=input_pdf,
        output_dir=output_dir,
        dpi=450,
    )

    assert calls == [
        ("render", input_pdf, output_dir / "pages", 450),
        ("ocr", rendered_paths, output_dir, False),
    ]
