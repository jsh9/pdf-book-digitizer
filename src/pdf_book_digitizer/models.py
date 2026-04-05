from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class BoundingBox:
    left: int
    top: int
    right: int
    bottom: int

    def clamp(self, width: int, height: int) -> "BoundingBox":
        return BoundingBox(
            left=max(0, min(self.left, width)),
            top=max(0, min(self.top, height)),
            right=max(0, min(self.right, width)),
            bottom=max(0, min(self.bottom, height)),
        )

    @property
    def width(self) -> int:
        return max(0, self.right - self.left)

    @property
    def height(self) -> int:
        return max(0, self.bottom - self.top)


@dataclass(slots=True)
class PageImageRegion:
    index: int
    caption: str
    bbox: BoundingBox
    asset_name: str | None = None


@dataclass(slots=True)
class PageContent:
    page_number: int
    body_markdown: str
    running_header: str = ""
    running_footer: str = ""
    printed_page_number: str = ""
    images: list[PageImageRegion] = field(default_factory=list)

