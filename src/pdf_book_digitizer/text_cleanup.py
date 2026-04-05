from __future__ import annotations

import re


def unwrap_ocr_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return ""

    paragraphs = re.split(r"\n\s*\n+", normalized)
    cleaned_paragraphs = [_collapse_paragraph_lines(paragraph) for paragraph in paragraphs]
    return "\n".join(paragraph for paragraph in cleaned_paragraphs if paragraph)


def _collapse_paragraph_lines(paragraph: str) -> str:
    lines = [line.strip() for line in paragraph.split("\n") if line.strip()]
    if not lines:
        return ""
    return " ".join(lines)
