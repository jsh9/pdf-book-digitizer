from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PageContent:
    page_number: int
    body_markdown: str
