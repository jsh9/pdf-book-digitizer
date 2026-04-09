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
    """Convert one raw OCR page into processed Markdown plus extracted figures.

    The input is the raw page text returned by the OCR model, including
    region tags such as ``<|ref|>text`` and bounding boxes encoded in
    ``<|det|>`` markers. This function parses those regions, removes the
    structural tags from text blocks, normalizes OCR line wrapping, crops
    figure regions from the source page image, inserts Markdown image links
    at the corresponding positions, and optionally appends Markdown footnotes
    derived from a follow-up ``Free OCR.`` pass.

    Parameters
    ----------
    raw_markdown : str
        Raw OCR output for one page, including region tags.
    page_image_path : Path
        Path to the original page JPEG used for OCR.
    output_stem : str
        File stem used to name extracted figure images.
    figures_dir : Path
        Directory where figure crops should be written.
    figure_href_prefix : str
        Relative Markdown path prefix used for figure links.
    ocr_client : OllamaOCRClient | None, optional
        OCR client used only when footnote markers require a second
        ``Free OCR.`` extraction pass.

    Returns
    -------
    ProcessedPage
        The final Markdown plus any cropped figure image paths written during
        processing.
    """
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
            extract_image_by_coord(page_image_path, region.bbox, figure_path)
            figure_paths.append(figure_path)
            blocks.append(f"![]({figure_href_prefix}{figure_path.name})")
            continue

        if region.ref_type == "image_caption":
            caption = normalize_ocr_text(region.content)
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
    """Parse tagged OCR output into ordered regions.

    The raw OCR format alternates region header lines such as
    ``<|ref|>text<|/ref|><|det|>[[...]]<|/det|>`` with the corresponding
    content lines that belong to that region. This function groups those
    lines together while preserving the original order so later processing
    can reconstruct the page from top to bottom.

    Parameters
    ----------
    raw_markdown : str
        Raw OCR text for one page.

    Returns
    -------
    list[OCRRegion]
        Parsed regions containing the detected region type, optional bounding
        box, and associated content.
    """
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
    """Render one non-image OCR region into Markdown text.

    Plain text regions are normalized for paragraph structure, while title
    and subtitle regions are additionally coerced to the expected Markdown
    heading level.

    Parameters
    ----------
    region : OCRRegion
        Parsed OCR region that is not an image block.

    Returns
    -------
    str
        Markdown text for the region, or an empty string when the region
        contains no meaningful content after normalization.
    """
    text = normalize_ocr_text(region.content)
    if not text:
        return ""
    if region.ref_type == "title":
        return normalize_heading(text, level=1)
    if region.ref_type == "sub_title":
        return normalize_heading(text, level=2)
    return text


def normalize_ocr_text(text: str) -> str:
    """Normalize regular OCR text into paragraph-oriented Markdown prose.

    This function is the main-body normalization path. It removes terminal
    control garbage such as ``\\x1b[K``, joins a line with the next line when
    that garbage signals a visual wrap, and treats a clean line ending as the
    end of a paragraph. Paragraphs are separated with blank lines in the
    returned Markdown text.

    Parameters
    ----------
    text : str
        Raw OCR text content for a body, title, or caption region.

    Returns
    -------
    str
        Normalized text with visual line wraps collapsed and paragraphs
        separated by ``\\n\\n``.
    """
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
    """Normalize a heading to the requested Markdown heading level.

    Any existing leading ``#`` markers are stripped before the heading is
    rebuilt so that the result has exactly the requested level.

    Parameters
    ----------
    text : str
        OCR text believed to represent a heading.
    level : int
        Desired Markdown heading level, typically 1 or 2.

    Returns
    -------
    str
        A Markdown heading string such as ``# Title`` or ``## Subtitle``.
    """
    stripped = text.strip()
    if not stripped:
        return ""
    stripped = re.sub(r"^#+\s*", "", stripped)
    return f"{'#' * level} {stripped}"


def extract_image_by_coord(page_image_path: Path, bbox: tuple[int, int, int, int], output_path: Path) -> None:
    """Crop a figure from a page image using OCR-provided relative coordinates.

    The OCR model emits figure bounding boxes in 0-1000 relative coordinates.
    This function converts that box to pixel coordinates, crops the region
    from the source page image, and saves the crop as a JPEG file.

    Parameters
    ----------
    page_image_path : Path
        Source page image.
    bbox : tuple[int, int, int, int]
        Relative OCR bounding box ``(left, top, right, bottom)``.
    output_path : Path
        Destination path for the cropped figure JPEG.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(page_image_path) as page_image:
        width, height = page_image.size
        left, top, right, bottom = scale_relative_bbox(bbox, width, height)
        cropped = page_image.crop((left, top, right, bottom))
        cropped.save(output_path, format="JPEG", quality=95)


def scale_relative_bbox(bbox: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
    """Convert OCR relative coordinates into clamped pixel coordinates.

    The OCR model expresses region coordinates in the range 0-1000 relative
    to page width and height. This helper maps those values to pixel space,
    clamps them to image bounds, and guarantees a non-empty box.

    Parameters
    ----------
    bbox : tuple[int, int, int, int]
        Relative OCR bounding box ``(left, top, right, bottom)``.
    width : int
        Source image width in pixels.
    height : int
        Source image height in pixels.

    Returns
    -------
    tuple[int, int, int, int]
        Pixel bounding box suitable for PIL cropping.
    """
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
    """Clamp one coordinate to the inclusive image bounds.

    Parameters
    ----------
    value : int
        Candidate pixel coordinate.
    extent : int
        Maximum image extent for that axis.

    Returns
    -------
    int
        Coordinate constrained to ``0 <= value <= extent``.
    """
    return max(0, min(value, extent))


def contains_footnote_marker(text: str) -> bool:
    """Return whether text contains any supported circled footnote marker.

    Parameters
    ----------
    text : str
        Text to scan.

    Returns
    -------
    bool
        ``True`` when any of the supported circled markers such as ``①`` or
        ``②`` appears in the text, otherwise ``False``.
    """
    return any(marker in text for marker in FOOTNOTE_MARKERS)


def add_markdown_footnotes(markdown: str, page_image_path: Path, ocr_client: OllamaOCRClient | None) -> str:
    """Append Markdown footnote definitions using a secondary Free OCR pass.

    When circled markers such as ``①`` appear in the processed page body, the
    normal OCR output is assumed to be missing the actual footnote text.
    This function requests a second OCR pass using the ``Free OCR.`` prompt,
    normalizes that output for footnote extraction, extracts the footnote
    bodies, converts inline circled markers in the page body to Markdown
    footnote references, and appends Markdown footnote definitions.

    Parameters
    ----------
    markdown : str
        Processed page Markdown before footnote expansion.
    page_image_path : Path
        Source page image used for the secondary OCR pass.
    ocr_client : OllamaOCRClient | None
        OCR client capable of running ``free_ocr_page_text()``.

    Returns
    -------
    str
        Original Markdown when no footnotes are detected, otherwise Markdown
        with inline markers replaced and footnote definitions appended.
    """
    if not markdown or not contains_footnote_marker(markdown):
        return markdown

    if ocr_client is None:
        raise ValueError("Footnote markers were found but no OCR client was provided for Free OCR reprocessing.")

    text_extracted_by_free_ocr = ocr_client.free_ocr_page_text(page_image_path)
    normalized_text = normalize_ocr_test_to_extract_footnote(text_extracted_by_free_ocr)
    footnotes = extract_footnotes_from_free_ocr(normalized_text)
    converted_markdown = replace_footnote_markers(markdown)
    if not footnotes:
        return converted_markdown

    ordered_markers = []
    for marker in FOOTNOTE_MARKERS:
        if marker in markdown and marker in footnotes:
            ordered_markers.append(marker)

    definitions = [
        format_markdown_footnote_definition(footnote_marker_to_number(marker), replace_footnote_markers(footnotes[marker]))
        for marker in ordered_markers
    ]
    if not definitions:
        return converted_markdown
    return f"{converted_markdown}\n\n" + "\n".join(definitions)


def extract_footnotes_from_free_ocr(normalized_text: str) -> dict[str, str]:
    """Extract footnote bodies from normalized Free OCR text.

    The extraction strategy intentionally searches backward by taking the last
    occurrence of each circled marker such as ``①`` and ``②``. This avoids
    confusing inline call sites in the main body with the actual footnote
    definitions that typically appear later on the page.

    Parameters
    ----------
    normalized_text : str
        Free OCR output after footnote-specific normalization.

    Returns
    -------
    dict[str, str]
        Mapping from circled marker to extracted footnote body text.
    """
    last_positions: dict[str, int] = {}
    for marker in FOOTNOTE_MARKERS:
        position = normalized_text.rfind(marker)
        if position != -1:
            last_positions[marker] = position

    if not last_positions:
        return {}

    ordered_positions = sorted((position, marker) for marker, position in last_positions.items())
    footnotes: dict[str, str] = {}

    for index, (start, marker) in enumerate(ordered_positions):
        end = ordered_positions[index + 1][0] if index + 1 < len(ordered_positions) else len(normalized_text)
        content = normalized_text[start + len(marker) : end].strip()
        if content:
            footnotes[marker] = content

    return footnotes


def normalize_ocr_test_to_extract_footnote(text: str) -> str:
    """Normalize Free OCR text for footnote extraction without collapsing real line breaks.

    This is intentionally different from `normalize_ocr_text()`.

    `normalize_ocr_text()` is designed for body text and treats any clean
    line ending as the end of a paragraph. That would be too aggressive for
    footnotes, because a footnote body can legitimately span multiple lines
    even when those lines do not contain terminal-control garbage.

    This function therefore:
    - removes escape/control garbage such as ``\\x1b[K``
    - joins only lines whose wrap is explicitly signaled by that garbage
    - preserves ordinary clean line breaks inside a paragraph

    The result is suitable for `extract_footnotes_from_free_ocr()`, which
    relies on the last occurrences of circled markers like ``①`` and ``②``
    while preserving multiline footnote content.

    Parameters
    ----------
    text : str
        Raw text returned by the ``Free OCR.`` prompt.

    Returns
    -------
    str
        Text with OCR control garbage removed and explicit wrap joins applied,
        while still preserving genuine multiline footnote structure.
    """
    paragraphs: list[str] = []
    current_lines: list[str] = []
    previous_had_escape = False

    for raw_line in text.splitlines():
        if not raw_line.strip():
            if current_lines:
                paragraphs.append("\n".join(current_lines))
                current_lines = []
            previous_had_escape = False
            continue

        cleaned_line = ESCAPE_SEQUENCE_PATTERN.sub("", raw_line).strip()
        cleaned_line = CENTER_TAG_PATTERN.sub("", cleaned_line).strip()
        if not cleaned_line:
            previous_had_escape = False
            continue

        if not current_lines:
            current_lines.append(cleaned_line)
        elif previous_had_escape:
            current_lines[-1] += cleaned_line
        else:
            current_lines.append(cleaned_line)

        previous_had_escape = "\x1b" in raw_line

    if current_lines:
        paragraphs.append("\n".join(current_lines))

    return "\n\n".join(paragraphs)


def replace_footnote_markers(text: str) -> str:
    """Convert circled inline markers into Markdown footnote references.

    Parameters
    ----------
    text : str
        Text containing circled markers such as ``①`` and ``②``.

    Returns
    -------
    str
        Text with those markers replaced by Markdown references such as
        ``[^1]`` and ``[^2]``.
    """
    replaced = text
    for marker in FOOTNOTE_MARKERS:
        replaced = replaced.replace(marker, f"[^{footnote_marker_to_number(marker)}]")
    return replaced


def footnote_marker_to_number(marker: str) -> int:
    """Map a circled marker to its 1-based numeric footnote index.

    Parameters
    ----------
    marker : str
        Circled marker character such as ``①``.

    Returns
    -------
    int
        The 1-based numeric index associated with that marker.
    """
    return FOOTNOTE_MARKERS.index(marker) + 1


def format_markdown_footnote_definition(number: int, content: str) -> str:
    """Format one Markdown footnote definition.

    Multiline footnote content is rendered using indented continuation lines
    so the output remains valid Markdown footnote syntax.

    Parameters
    ----------
    number : int
        Numeric footnote index.
    content : str
        Footnote body text.

    Returns
    -------
    str
        Markdown footnote definition string.
    """
    lines = content.splitlines()
    if not lines:
        return f"[^{number}]:"
    if len(lines) == 1:
        return f"[^{number}]: {lines[0]}"
    indented_tail = "\n".join(f"    {line}" for line in lines[1:])
    return f"[^{number}]: {lines[0]}\n{indented_tail}"
