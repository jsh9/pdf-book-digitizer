from __future__ import annotations

from pathlib import Path

from pdf_book_digitizer.models import PageContent


def write_page_markdown(page: PageContent, output_path: Path) -> None:
    lines: list[str] = []
    if page.running_header:
        lines.append(f"Header: {page.running_header}")
    if page.running_footer:
        lines.append(f"Footer: {page.running_footer}")
    if page.printed_page_number:
        lines.append(f"Printed page number: {page.printed_page_number}")
    if lines:
        lines.append("")
    lines.append(page.body_markdown)
    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def read_page_markdown(input_path: Path, page_number: int) -> PageContent:
    lines = input_path.read_text(encoding="utf-8").splitlines()
    running_header = ""
    running_footer = ""
    printed_page_number = ""
    body_start = 0

    for index, line in enumerate(lines):
        if not line:
            body_start = index + 1
            break
        if line.startswith("Header: "):
            running_header = line.removeprefix("Header: ")
            continue
        if line.startswith("Footer: "):
            running_footer = line.removeprefix("Footer: ")
            continue
        if line.startswith("Printed page number: "):
            printed_page_number = line.removeprefix("Printed page number: ")
            continue
        body_start = index
        break
    body_markdown = "\n".join(lines[body_start:]).strip()
    return PageContent(
        page_number=page_number,
        body_markdown=body_markdown,
        running_header=running_header,
        running_footer=running_footer,
        printed_page_number=printed_page_number,
        images=[],
    )
