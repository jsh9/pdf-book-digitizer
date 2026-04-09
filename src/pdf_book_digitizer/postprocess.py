from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from pdf_book_digitizer.ocr import OllamaOCRClient


TAG_LINE_PATTERN = re.compile(
    r"^<\|ref\|>(?P<ref_type>[^<]+)<\|/ref\|><\|det\|>\[\[(?P<left>\d+), (?P<top>\d+), (?P<right>\d+), (?P<bottom>\d+)\]\]<\|/det\|>\s*$"
)
ESCAPE_SEQUENCE_PATTERN = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
CENTER_TAG_PATTERN = re.compile(r"</?center>")
FOOTNOTE_MARKERS = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
FOOTNOTE_SEGMENT_PATTERN = re.compile(
    rf"([{FOOTNOTE_MARKERS}])\s*(.+?)(?=(?:[{FOOTNOTE_MARKERS}])|$)"
)


@dataclass(slots=True)
class OCRRegion:
    ref_type: str
    bbox: tuple[int, int, int, int] | None
    content: str


@dataclass(slots=True)
class ProcessedPage:
    markdown: str
    figure_paths: list[Path]


def postprocess_page(
    raw_markdown: str,
    page_image_path: Path,
    output_stem: str,
    figures_dir: Path,
    figure_href_prefix: str,
    ocr_client: OllamaOCRClient | None = None,
) -> ProcessedPage:
    regions = parse_ocr_regions(raw_markdown)
    figure_paths: list[Path] = []
    blocks: list[str] = []
    figure_index = 0

    for region in regions:
        if region.ref_type == "image":
            if region.bbox is None:
                continue
            figure_index += 1
            figure_path = figures_dir / f"{output_stem}-fig-{figure_index:03d}.jpg"
            crop_image_region(page_image_path, region.bbox, figure_path)
            figure_paths.append(figure_path)
            blocks.append(f"![]({figure_href_prefix}{figure_path.name})")
            continue

        if region.ref_type == "image_caption":
            caption = reconstruct_paragraphs(region.content)
            caption = CENTER_TAG_PATTERN.sub("", caption).strip()
            if caption:
                blocks.append(caption)
            continue

        block = render_text_region(region)
        if block:
            blocks.append(block)

    markdown = "\n\n".join(block.strip() for block in blocks if block.strip())
    markdown = add_markdown_footnotes(markdown, page_image_path, ocr_client)
    return ProcessedPage(markdown=markdown.strip(), figure_paths=figure_paths)


def parse_ocr_regions(raw_markdown: str) -> list[OCRRegion]:
    regions: list[OCRRegion] = []
    current_ref_type = "text"
    current_bbox: tuple[int, int, int, int] | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_ref_type, current_bbox, current_lines
        if not current_lines and current_bbox is None and not regions:
            return
        content = "\n".join(current_lines).strip()
        if content or current_bbox is not None:
            regions.append(OCRRegion(ref_type=current_ref_type, bbox=current_bbox, content=content))
        current_ref_type = "text"
        current_bbox = None
        current_lines = []

    for line in raw_markdown.splitlines():
        match = TAG_LINE_PATTERN.match(line.strip())
        if match:
            flush()
            current_ref_type = match.group("ref_type")
            current_bbox = (
                int(match.group("left")),
                int(match.group("top")),
                int(match.group("right")),
                int(match.group("bottom")),
            )
            continue
        current_lines.append(line)

    flush()
    return regions


def render_text_region(region: OCRRegion) -> str:
    text = reconstruct_paragraphs(region.content)
    if not text:
        return ""
    if region.ref_type == "title":
        return normalize_heading(text, level=1)
    if region.ref_type == "sub_title":
        return normalize_heading(text, level=2)
    return text


def reconstruct_paragraphs(text: str) -> str:
    paragraphs: list[str] = []
    current = ""

    for raw_line in text.splitlines():
        stripped_line = raw_line.strip()
        if not stripped_line:
            if current:
                paragraphs.append(current.strip())
                current = ""
            continue

        cleaned_line = ESCAPE_SEQUENCE_PATTERN.sub("", raw_line).strip()
        cleaned_line = CENTER_TAG_PATTERN.sub("", cleaned_line).strip()
        if not cleaned_line:
            continue

        current += cleaned_line
        if "\x1b" not in raw_line:
            paragraphs.append(current.strip())
            current = ""

    if current:
        paragraphs.append(current.strip())

    return "\n\n".join(paragraph for paragraph in paragraphs if paragraph)


def normalize_heading(text: str, level: int) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    stripped = re.sub(r"^#+\s*", "", stripped)
    return f"{'#' * level} {stripped}"


def crop_image_region(page_image_path: Path, bbox: tuple[int, int, int, int], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(page_image_path) as page_image:
        width, height = page_image.size
        left, top, right, bottom = scale_relative_bbox(bbox, width, height)
        cropped = page_image.crop((left, top, right, bottom))
        cropped.save(output_path, format="JPEG", quality=95)


def scale_relative_bbox(bbox: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
    left = clamp_pixel(math.floor(width * bbox[0] / 1000), width)
    top = clamp_pixel(math.floor(height * bbox[1] / 1000), height)
    right = clamp_pixel(math.ceil(width * bbox[2] / 1000), width)
    bottom = clamp_pixel(math.ceil(height * bbox[3] / 1000), height)

    if right <= left:
        right = min(width, left + 1)
    if bottom <= top:
        bottom = min(height, top + 1)
    return left, top, right, bottom


def clamp_pixel(value: int, extent: int) -> int:
    return max(0, min(value, extent))


def contains_footnote_marker(text: str) -> bool:
    return any(marker in text for marker in FOOTNOTE_MARKERS)


def add_markdown_footnotes(markdown: str, page_image_path: Path, ocr_client: OllamaOCRClient | None) -> str:
    if not markdown or not contains_footnote_marker(markdown):
        return markdown
    if ocr_client is None:
        raise ValueError("Footnote markers were found but no OCR client was provided for Free OCR reprocessing.")

    footnotes = extract_footnotes_from_free_ocr(ocr_client.free_ocr_page_text(page_image_path))
    converted_markdown = replace_footnote_markers(markdown)
    if not footnotes:
        return converted_markdown

    ordered_markers = []
    for marker in FOOTNOTE_MARKERS:
        if marker in markdown and marker in footnotes:
            ordered_markers.append(marker)

    definitions = [
        f"[^{footnote_marker_to_number(marker)}]: {replace_footnote_markers(footnotes[marker])}"
        for marker in ordered_markers
    ]
    if not definitions:
        return converted_markdown
    return f"{converted_markdown}\n\n" + "\n".join(definitions)


def extract_footnotes_from_free_ocr(text: str) -> dict[str, str]:
    normalized = reconstruct_paragraphs(text)
    footnotes: dict[str, str] = {}
    for paragraph in normalized.split("\n\n"):
        if not contains_footnote_marker(paragraph):
            continue
        for marker, content in FOOTNOTE_SEGMENT_PATTERN.findall(paragraph):
            cleaned_content = content.strip()
            if cleaned_content and marker not in footnotes:
                footnotes[marker] = cleaned_content
    return footnotes


def replace_footnote_markers(text: str) -> str:
    replaced = text
    for marker in FOOTNOTE_MARKERS:
        replaced = replaced.replace(marker, f"[^{footnote_marker_to_number(marker)}]")
    return replaced


def footnote_marker_to_number(marker: str) -> int:
    return FOOTNOTE_MARKERS.index(marker) + 1
