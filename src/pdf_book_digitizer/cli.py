from __future__ import annotations

import argparse
from pathlib import Path

from pdf_book_digitizer.config import DigitizerConfig
from pdf_book_digitizer.pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Digitize a scanned PDF book into OCR text and extracted images.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("input_pdf", type=Path, help="Path to the source PDF file.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory for generated assets. An `ocr/` subfolder will be created under this directory.",
    )
    parser.add_argument("--model", default="glm-ocr", help="Ollama model name to use for OCR.")
    parser.add_argument("--dpi", type=int, default=300, help="Rasterization DPI.")
    parser.add_argument(
        "--image-min-width-ratio",
        type=float,
        default=0.12,
        help="Discard detected image crops narrower than this fraction of the page width.",
    )
    parser.add_argument(
        "--image-min-height-ratio",
        type=float,
        default=0.08,
        help="Discard detected image crops shorter than this fraction of the page height.",
    )
    parser.add_argument("--language-hint", default="", help="Optional language hint to include in the OCR prompt.")
    parser.add_argument(
        "--unwrap-text",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Unwrap OCR text by joining hard-wrapped lines and using single newlines between paragraphs.",
    )
    parser.add_argument(
        "--output-json",
        action="store_true",
        help="Write per-page OCR results as JSON files instead of Markdown.",
    )
    parser.add_argument(
        "--llm-refix",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run LLM-based cleanup and hard-line-break re-fix passes after OCR.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    config = DigitizerConfig(
        input_pdf=args.input_pdf,
        output_dir=args.output_dir,
        model=args.model,
        dpi=args.dpi,
        image_min_width_ratio=args.image_min_width_ratio,
        image_min_height_ratio=args.image_min_height_ratio,
        language_hint=args.language_hint,
        unwrap_text=args.unwrap_text,
        output_json=args.output_json,
        llm_refix=args.llm_refix,
    )
    run_pipeline(config)


if __name__ == "__main__":
    main()
