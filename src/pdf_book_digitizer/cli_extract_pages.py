from __future__ import annotations

import argparse
from pathlib import Path

from pdf_book_digitizer.pdf_render import render_pdf_to_jpgs


def build_parser() -> argparse.ArgumentParser:
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


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    render_pdf_to_jpgs(args.input_pdf, args.output_dir, args.dpi)


if __name__ == "__main__":
    main()
