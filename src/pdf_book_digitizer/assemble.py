from __future__ import annotations

import html
import json
from pathlib import Path

from pdf_book_digitizer.models import PageContent


def write_page_json(page: PageContent, output_path: Path) -> None:
    payload = {
        "page_number": page.page_number,
        "running_header": page.running_header,
        "running_footer": page.running_footer,
        "printed_page_number": page.printed_page_number,
        "body_markdown": page.body_markdown,
        "images": [
            {
                "index": image.index,
                "caption": image.caption,
                "asset_name": image.asset_name,
                "bbox": {
                    "left": image.bbox.left,
                    "top": image.bbox.top,
                    "right": image.bbox.right,
                    "bottom": image.bbox.bottom,
                },
            }
            for image in page.images
        ],
    }
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


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


def read_page_json(input_path: Path) -> PageContent:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    return PageContent(
        page_number=int(payload.get("page_number", 0)),
        body_markdown=payload.get("body_markdown", ""),
        running_header=payload.get("running_header", ""),
        running_footer=payload.get("running_footer", ""),
        printed_page_number=payload.get("printed_page_number", ""),
        images=[],
    )


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


def assemble_html_document(pages: list[PageContent], output_path: Path) -> None:
    page_sections = "\n".join(_render_page(page) for page in pages)
    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Digitized Book</title>
  <style>
    body {{
      font-family: Georgia, "Times New Roman", serif;
      line-height: 1.6;
      margin: 2rem auto;
      max-width: 48rem;
      padding: 0 1rem 4rem;
    }}
    .page-break {{
      border-top: 1px solid #bbb;
      margin: 2rem 0;
      padding-top: 2rem;
    }}
    .page-meta {{
      color: #666;
      font-size: 0.9rem;
      margin-bottom: 1rem;
    }}
    figure {{
      margin: 1.5rem 0;
    }}
    img {{
      display: block;
      height: auto;
      max-width: 100%;
    }}
    figcaption {{
      color: #555;
      font-size: 0.95rem;
      margin-top: 0.5rem;
    }}
    pre {{
      white-space: pre-wrap;
      word-break: break-word;
    }}
  </style>
</head>
<body>
{page_sections}
</body>
</html>
"""
    output_path.write_text(html_doc, encoding="utf-8")


def assemble_markdown_document(pages: list[PageContent], output_path: Path) -> None:
    sections = [_render_page_markdown(page) for page in pages]
    output_path.write_text("\n\n".join(section.rstrip() for section in sections).rstrip() + "\n", encoding="utf-8")


def _render_page(page: PageContent) -> str:
    meta_parts = []
    if page.printed_page_number:
        meta_parts.append(f"Printed page {html.escape(page.printed_page_number)}")
    if page.running_header:
        meta_parts.append(f"Header: {html.escape(page.running_header)}")
    if page.running_footer:
        meta_parts.append(f"Footer: {html.escape(page.running_footer)}")
    meta = " | ".join(meta_parts)
    images = "\n".join(_render_image(page, image.asset_name, image.caption) for image in page.images if image.asset_name)
    body = html.escape(page.body_markdown)
    meta_html = f'<div class="page-meta">{meta}</div>' if meta else ""
    return f"""<section class="page-break" id="page-{page.page_number}">
  <h2>Page {page.page_number}</h2>
  {meta_html}
  <pre>{body}</pre>
  {images}
</section>"""


def _render_page_markdown(page: PageContent) -> str:
    lines = [f"## Page {page.page_number}"]
    if page.printed_page_number:
        lines.append(f"Printed page: {page.printed_page_number}")
    if page.running_header:
        lines.append(f"Header: {page.running_header}")
    if page.running_footer:
        lines.append(f"Footer: {page.running_footer}")
    if len(lines) > 1:
        lines.append("")
    lines.append(page.body_markdown)
    return "\n".join(lines)


def _render_image(page: PageContent, asset_name: str | None, caption: str) -> str:
    if not asset_name:
        return ""
    escaped_caption = html.escape(caption)
    caption_html = f"<figcaption>{escaped_caption}</figcaption>" if escaped_caption else ""
    return f"""<figure>
  <img src="images/{asset_name}" alt="Illustration from page {page.page_number}">
  {caption_html}
</figure>"""
