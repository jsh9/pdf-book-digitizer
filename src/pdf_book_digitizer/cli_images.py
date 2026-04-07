from __future__ import annotations

import argparse
from pathlib import Path

from pdf_book_digitizer.image_inputs import collect_image_paths
from pdf_book_digitizer.pipeline import run_ocr_from_images


def build_parser() -> argparse.ArgumentParser:
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


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    image_paths = collect_image_paths(args.images_dir)
    run_ocr_from_images(
        image_paths=image_paths,
        output_dir=args.output_dir,
        preserve_input_names=True,
    )


if __name__ == "__main__":
    main()
