from __future__ import annotations

import argparse
from pathlib import Path

from pdf_book_digitizer.image_inputs import collect_image_paths
from pdf_book_digitizer.pipeline import run_ocr_from_images


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="OCR a folder of page images into per-page JSON and book HTML.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("images_dir", type=Path, help="Directory containing page images to OCR.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory for generated assets. The command reads from and writes to an `ocr/` subfolder under this directory.",
    )
    parser.add_argument("--model", default="glm-ocr", help="Ollama model name to use for OCR.")
    parser.add_argument("--language-hint", default="", help="Optional language hint to include in the OCR prompt.")
    parser.add_argument(
        "--unwrap-text",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Unwrap OCR text by joining hard-wrapped lines and using single newlines between paragraphs.",
    )
    parser.add_argument(
        "--llm-fix",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run an LLM cleanup pass on raw OCR text immediately after OCR.",
    )
    parser.add_argument(
        "--output-json",
        action="store_true",
        help="Write per-page OCR results as JSON files instead of Markdown.",
    )
    parser.add_argument(
        "--llm-refix",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Run the later hard-line-break re-fix pass after the initial OCR output is written.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    image_paths = collect_image_paths(args.images_dir)
    run_ocr_from_images(
        image_paths=image_paths,
        output_dir=args.output_dir,
        model=args.model,
        language_hint=args.language_hint,
        unwrap_text=args.unwrap_text,
        output_json=args.output_json,
        llm_fix=args.llm_fix,
        llm_refix=args.llm_refix,
        preserve_input_names=True,
    )


if __name__ == "__main__":
    main()
