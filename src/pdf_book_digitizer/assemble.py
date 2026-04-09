from __future__ import annotations

from pathlib import Path

from pdf_book_digitizer.models import PageContent


def write_page_markdown(page: PageContent, output_path: Path) -> None:
    output_path.write_text(page.body_markdown.rstrip() + "\n", encoding="utf-8")


def read_page_markdown(input_path: Path, page_number: int) -> PageContent:
    body_markdown = input_path.read_text(encoding="utf-8").strip()
    return PageContent(
        page_number=page_number,
        body_markdown=body_markdown,
    )
