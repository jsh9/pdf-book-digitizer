from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from pdf_book_digitizer.assemble import (
    assemble_markdown_document,
    assemble_html_document,
    read_page_json,
    read_page_markdown,
    write_page_json,
    write_page_markdown,
)
from pdf_book_digitizer.config import DigitizerConfig
from pdf_book_digitizer.diffs import build_unified_diff, write_diff
from pdf_book_digitizer.hard_line_breaks import needs_hard_line_break_fix
from pdf_book_digitizer.image_inputs import infer_page_number_from_image_path
from pdf_book_digitizer.models import PageContent
from pdf_book_digitizer.ocr import OllamaOCRClient
from pdf_book_digitizer.pdf_render import render_pdf_to_jpgs
from pdf_book_digitizer.text_fix import fix_ocr_text_with_LLM
from pdf_book_digitizer.text_cleanup import unwrap_ocr_text


INITIAL_RECHECK_PASS_NUMBER = 2


def run_pipeline(config: DigitizerConfig) -> None:
    pages_dir = config.output_dir / "pages"
    page_images = render_pdf_to_jpgs(config.input_pdf, pages_dir, config.dpi)
    run_ocr_from_images(
        image_paths=page_images,
        output_dir=config.output_dir,
        model=config.model,
        language_hint=config.language_hint,
        unwrap_text=config.unwrap_text,
        output_json=config.output_json,
        llm_refix=config.llm_refix,
        preserve_input_names=False,
    )


def fix_raw_ocr_results(
    output_dir: Path,
    unwrap_text: bool = True,
    model: str = "qwen3.5:9b",
) -> None:
    ocr_dir = output_dir / "ocr"
    raw_dir = ocr_dir / "raw"
    fixed_dir = ocr_dir / "fixed"
    diffs_dir = ocr_dir / "diff"

    raw_paths, output_json = _collect_raw_page_paths(raw_dir)
    fixed_dir.mkdir(parents=True, exist_ok=True)
    diffs_dir.mkdir(parents=True, exist_ok=True)

    assembled_pages: list[PageContent] = []
    output_stems: list[str] = []

    for index, raw_path in enumerate(raw_paths, start=1):
        output_stem = raw_path.stem
        page_number = infer_page_number_from_image_path(raw_path, index)
        raw_page = _read_page_output(raw_path, page_number, output_json)
        original_text = raw_page.body_markdown
        fixed_text = fix_ocr_text_with_LLM(original_text, model=model)
        fixed_output_path = _build_output_path(fixed_dir, output_stem, output_json)
        diff_output_path = diffs_dir / f"{output_stem}.diff"

        assembled_page = replace(raw_page, body_markdown=fixed_text)
        if unwrap_text:
            assembled_page.body_markdown = unwrap_ocr_text(assembled_page.body_markdown)

        _write_page_output(assembled_page, fixed_output_path, output_json)
        diff_text = build_unified_diff(original_text, assembled_page.body_markdown, output_stem)
        write_diff(diff_text, diff_output_path)
        print(diff_text if diff_text else f"No fix diff for {output_stem}")

        assembled_pages.append(assembled_page)
        output_stems.append(output_stem)

    _rerun_hard_line_break_fix_passes(
        assembled_pages=assembled_pages,
        output_stems=output_stems,
        fixed_dir=fixed_dir,
        diffs_dir=diffs_dir,
        output_json=output_json,
        unwrap_text=unwrap_text,
        max_passes=1,
        model=model,
        write_unwrapped_fixed_output=True,
    )

    assemble_markdown_document(assembled_pages, output_dir / "book.md")
    assemble_html_document(assembled_pages, output_dir / "book.html")


def run_ocr_from_images(
    image_paths: list[Path],
    output_dir: Path,
    model: str,
    language_hint: str = "",
    unwrap_text: bool = True,
    output_json: bool = False,
    llm_refix: bool = True,
    preserve_input_names: bool = True,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    ocr_dir = output_dir / "ocr"
    raw_dir = ocr_dir / "raw"
    fixed_dir = ocr_dir / "fixed"
    diffs_dir = ocr_dir / "diff"
    ocr_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    fixed_dir.mkdir(parents=True, exist_ok=True)
    diffs_dir.mkdir(parents=True, exist_ok=True)

    client = OllamaOCRClient(model=model)
    assembled_pages = []
    output_stems: list[str] = []

    for index, page_image in enumerate(image_paths, start=1):
        output_stem = page_image.stem if preserve_input_names else f"page-{index:04d}"
        page_number = infer_page_number_from_image_path(page_image, index) if preserve_input_names else index
        fixed_output_path = _build_output_path(fixed_dir, output_stem, output_json)
        raw_output_path = _build_output_path(raw_dir, output_stem, output_json)
        diff_output_path = diffs_dir / f"{output_stem}.diff"

        if preserve_input_names and raw_dir.exists() and fixed_dir.exists() and diffs_dir.exists():
            if raw_output_path.exists() and fixed_output_path.exists() and diff_output_path.exists():
                print(f"Skipping {output_stem}; found existing raw, fixed, and diff outputs")
                assembled_pages.append(_read_page_output(fixed_output_path, page_number, output_json))
                output_stems.append(output_stem)
                continue

        page = client.ocr_page(page_image, page_number=page_number, language_hint=language_hint)
        original_text = page.body_markdown
        fixed_text = fix_ocr_text_with_LLM(original_text) if llm_refix else original_text
        raw_page = replace(page, body_markdown=original_text)
        fixed_page = replace(page, body_markdown=fixed_text)
        _write_page_output(raw_page, raw_output_path, output_json)
        _write_page_output(fixed_page, fixed_output_path, output_json)
        diff_text = build_unified_diff(original_text, fixed_text, output_stem)
        write_diff(diff_text, diff_output_path)
        if llm_refix:
            print(diff_text if diff_text else f"No fix diff for {output_stem}")
        else:
            print(f"Skipping LLM refix for {output_stem}; writing raw text as fixed output")
        page.body_markdown = fixed_text
        if unwrap_text:
            page.body_markdown = unwrap_ocr_text(page.body_markdown)
        assembled_pages.append(page)
        output_stems.append(output_stem)

    if llm_refix:
        _rerun_hard_line_break_fix_passes(
            assembled_pages=assembled_pages,
            output_stems=output_stems,
            fixed_dir=fixed_dir,
            diffs_dir=diffs_dir,
            output_json=output_json,
            unwrap_text=unwrap_text,
            max_passes=1,
            model="qwen3.5:9b",
            write_unwrapped_fixed_output=False,
        )
    else:
        print("Skipping hard-line-break recheck passes because LLM refix is disabled")

    assemble_markdown_document(assembled_pages, output_dir / "book.md")
    assemble_html_document(assembled_pages, output_dir / "book.html")


def _build_output_path(output_dir: Path, output_stem: str, output_json: bool) -> Path:
    if output_json:
        return output_dir / f"{output_stem}.json"
    return output_dir / f"{output_stem}.md"


def _write_page_output(page: PageContent, output_path: Path, output_json: bool) -> None:
    if output_json:
        write_page_json(page, output_path)
        return
    write_page_markdown(page, output_path)


def _read_page_output(input_path: Path, page_number: int, output_json: bool) -> PageContent:
    if output_json:
        return read_page_json(input_path)
    return read_page_markdown(input_path, page_number)


def _collect_raw_page_paths(raw_dir: Path) -> tuple[list[Path], bool]:
    if not raw_dir.exists():
        raise FileNotFoundError(f"Raw OCR directory does not exist: {raw_dir}")
    if not raw_dir.is_dir():
        raise NotADirectoryError(f"Raw OCR path is not a directory: {raw_dir}")

    json_paths = sorted(path for path in raw_dir.iterdir() if path.is_file() and path.suffix.lower() == ".json")
    markdown_paths = sorted(path for path in raw_dir.iterdir() if path.is_file() and path.suffix.lower() == ".md")

    if json_paths and markdown_paths:
        raise ValueError(f"Raw OCR directory contains both Markdown and JSON page artifacts: {raw_dir}")
    if json_paths:
        return json_paths, True
    if markdown_paths:
        return markdown_paths, False
    raise ValueError(f"No raw OCR page artifacts found in {raw_dir}")


def _rerun_hard_line_break_fix_passes(
    assembled_pages: list[PageContent],
    output_stems: list[str],
    fixed_dir: Path,
    diffs_dir: Path,
    output_json: bool,
    unwrap_text: bool,
    max_passes: int,
    model: str,
    write_unwrapped_fixed_output: bool,
) -> None:
    print(f"Starting hard-line-break recheck passes: {max_passes} total")
    # Pass 1 is the initial OCR cleanup that already produced `<stem>.diff`.
    # The follow-up hard-line-break pass therefore starts at pass 2 and writes
    # `<stem>-2.diff`.
    for pass_number in range(INITIAL_RECHECK_PASS_NUMBER, max_passes + INITIAL_RECHECK_PASS_NUMBER):
        print(f"Starting hard-line-break recheck pass {pass_number}")
        flagged_pages = 0
        for page, output_stem in zip(assembled_pages, output_stems, strict=True):
            fixed_output_path = _build_output_path(fixed_dir, output_stem, output_json)
            if not fixed_output_path.exists():
                print(f"Skipping hard-line-break recheck for {output_stem}; missing fixed output")
                continue

            stored_page = _read_page_output(fixed_output_path, page.page_number, output_json)
            if not needs_hard_line_break_fix(stored_page.body_markdown.splitlines()):
                print(f"No hard-line-break refix needed for {output_stem}; pass {pass_number}")
                continue

            flagged_pages += 1
            print(f"Re-fixing {output_stem} for hard line breaks; pass {pass_number}")
            refixed_text = fix_ocr_text_with_LLM(stored_page.body_markdown, model=model)
            print(f"Old content for {output_stem}; pass {pass_number}:\n{stored_page.body_markdown}")
            print(f"Fixed content for {output_stem}; pass {pass_number}:\n{refixed_text}")
            final_text = refixed_text
            if unwrap_text:
                final_text = unwrap_ocr_text(final_text)

            diff_text = build_unified_diff(stored_page.body_markdown, final_text, f"{output_stem}-{pass_number}")
            write_diff(diff_text, diffs_dir / f"{output_stem}-{pass_number}.diff")
            print(diff_text if diff_text else f"No refix diff for {output_stem}; pass {pass_number}")

            stored_page.body_markdown = final_text if write_unwrapped_fixed_output else refixed_text
            _write_page_output(stored_page, fixed_output_path, output_json)

            page.body_markdown = final_text

        if flagged_pages == 0:
            print(f"Completed hard-line-break recheck pass {pass_number}; no pages needed refix")
        else:
            print(f"Completed hard-line-break recheck pass {pass_number}; refixed {flagged_pages} page(s)")
    print("Completed all hard-line-break recheck passes")
