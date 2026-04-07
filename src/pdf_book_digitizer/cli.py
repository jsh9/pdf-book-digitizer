from __future__ import annotations

import argparse
from pathlib import Path

from pdf_book_digitizer.assemble import read_page_markdown, write_page_markdown
from pdf_book_digitizer.image_inputs import collect_image_paths, infer_page_number_from_image_path
from pdf_book_digitizer.manual_editor import main as manual_editor_main
from pdf_book_digitizer.models import PageContent
from pdf_book_digitizer.ocr import OllamaOCRClient
from pdf_book_digitizer.pdf_render import render_pdf_to_jpgs


def main() -> None:
    parser = build_digitize_book_parser()
    args = parser.parse_args()
    digitize_book(
        input_pdf=args.input_pdf,
        output_dir=args.output_dir,
        dpi=args.dpi,
    )


def digitize_book(input_pdf: Path, output_dir: Path, dpi: int) -> None:
    pages_dir = output_dir / "pages"
    page_images = render_pdf_to_jpgs(input_pdf, pages_dir, dpi)
    run_ocr_from_images(
        image_paths=page_images,
        output_dir=output_dir,
        preserve_input_names=False,
    )


def digitize_images_main() -> None:
    parser = build_digitize_images_parser()
    args = parser.parse_args()
    run_ocr_from_images(
        image_paths=collect_image_paths(args.images_dir),
        output_dir=args.output_dir,
        preserve_input_names=True,
    )


def extract_pdf_pages_main() -> None:
    parser = build_extract_pdf_pages_parser()
    args = parser.parse_args()
    render_pdf_to_jpgs(args.input_pdf, args.output_dir, args.dpi)


def inspect_ocr_pages_main() -> None:
    manual_editor_main()


def run_ocr_from_images(
    image_paths: list[Path],
    output_dir: Path,
    preserve_input_names: bool = True,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "ocr" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    client: OllamaOCRClient | None = None

    for index, page_image in enumerate(image_paths, start=1):
        output_stem = page_image.stem if preserve_input_names else f"page-{index:04d}"
        page_number = infer_page_number_from_image_path(page_image, index) if preserve_input_names else index
        raw_output_path = build_output_path(raw_dir, output_stem)

        if preserve_input_names and raw_output_path.exists():
            print(f"Skipping {output_stem}; found existing raw output")
            read_page_output(raw_output_path, page_number)
            continue

        if client is None:
            client = OllamaOCRClient()
        page = client.ocr_page(page_image, page_number=page_number)
        write_page_output(page, raw_output_path)
        print(f"Wrote raw OCR markdown for {output_stem}")


def build_digitize_book_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render a PDF into page images and OCR each page into Markdown.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("input_pdf", type=Path, help="Path to the source PDF file.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory for generated assets. The command writes page JPGs under `pages/` and OCR Markdown under `ocr/raw/`.",
    )
    parser.add_argument("--dpi", type=int, default=300, help="Rasterization DPI.")
    return parser


def build_digitize_images_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="OCR a folder of page images into per-page Markdown files.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("images_dir", type=Path, help="Directory containing page images to OCR.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory for generated assets. The command reads from and writes to an `ocr/raw/` subfolder under this directory.",
    )
    return parser


def build_extract_pdf_pages_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract one JPG image per page from a PDF.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("input_pdf", type=Path, help="Path to the source PDF file.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("pages"),
        help="Directory where extracted page JPG files will be written.",
    )
    parser.add_argument("--dpi", type=int, default=300, help="Rasterization DPI.")
    return parser


def build_output_path(output_dir: Path, output_stem: str) -> Path:
    return output_dir / f"{output_stem}.md"


def write_page_output(page: PageContent, output_path: Path) -> None:
    write_page_markdown(page, output_path)


def read_page_output(input_path: Path, page_number: int) -> PageContent:
    return read_page_markdown(input_path, page_number)


if __name__ == "__main__":
    main()
