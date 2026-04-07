from __future__ import annotations

import argparse
from pathlib import Path

from pdf_book_digitizer.config import DigitizerConfig
from pdf_book_digitizer.pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
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


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    config = DigitizerConfig(
        input_pdf=args.input_pdf,
        output_dir=args.output_dir,
        dpi=args.dpi,
    )
    run_pipeline(config)


if __name__ == "__main__":
    main()
