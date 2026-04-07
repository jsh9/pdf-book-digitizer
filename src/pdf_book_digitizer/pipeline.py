from __future__ import annotations

from pathlib import Path

from pdf_book_digitizer.assemble import read_page_markdown, write_page_markdown
from pdf_book_digitizer.config import DigitizerConfig
from pdf_book_digitizer.image_inputs import infer_page_number_from_image_path
from pdf_book_digitizer.models import PageContent
from pdf_book_digitizer.ocr import OllamaOCRClient
from pdf_book_digitizer.pdf_render import render_pdf_to_jpgs


def run_pipeline(config: DigitizerConfig) -> None:
    pages_dir = config.output_dir / "pages"
    page_images = render_pdf_to_jpgs(config.input_pdf, pages_dir, config.dpi)
    run_ocr_from_images(
        image_paths=page_images,
        output_dir=config.output_dir,
        preserve_input_names=False,
    )


def run_ocr_from_images(
    image_paths: list[Path],
    output_dir: Path,
    preserve_input_names: bool = True,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    ocr_dir = output_dir / "ocr"
    raw_dir = ocr_dir / "raw"
    ocr_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    client: OllamaOCRClient | None = None

    for index, page_image in enumerate(image_paths, start=1):
        output_stem = page_image.stem if preserve_input_names else f"page-{index:04d}"
        page_number = infer_page_number_from_image_path(page_image, index) if preserve_input_names else index
        raw_output_path = _build_output_path(raw_dir, output_stem)

        if preserve_input_names and raw_output_path.exists():
            print(f"Skipping {output_stem}; found existing raw output")
            _read_page_output(raw_output_path, page_number)
            continue

        if client is None:
            client = OllamaOCRClient()
        page = client.ocr_page(page_image, page_number=page_number)
        _write_page_output(page, raw_output_path)
        print(f"Wrote raw OCR markdown for {output_stem}")


def _build_output_path(output_dir: Path, output_stem: str) -> Path:
    return output_dir / f"{output_stem}.md"


def _write_page_output(page: PageContent, output_path: Path) -> None:
    write_page_markdown(page, output_path)


def _read_page_output(input_path: Path, page_number: int) -> PageContent:
    return read_page_markdown(input_path, page_number)
