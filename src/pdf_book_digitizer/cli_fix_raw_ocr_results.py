from __future__ import annotations

import argparse
from pathlib import Path

from pdf_book_digitizer.pipeline import fix_raw_ocr_results
from pdf_book_digitizer.text_fix import FIX_MODEL


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the OCR cleanup and hard-line-break re-fix passes on existing raw OCR page artifacts."
    )
    parser.add_argument(
        "output_dir",
        nargs="?",
        type=Path,
        default=Path("output"),
        help="Directory containing ocr/raw artifacts and where refreshed outputs will be written.",
    )
    parser.add_argument(
        "--model",
        default=FIX_MODEL,
        help="Ollama model name to use for OCR cleanup.",
    )
    parser.add_argument(
        "--unwrap-text",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Unwrap cleaned text in the assembled book outputs while leaving per-page fixed artifacts unchanged.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    fix_raw_ocr_results(
        output_dir=args.output_dir,
        unwrap_text=args.unwrap_text,
        model=args.model,
    )


if __name__ == "__main__":
    main()
