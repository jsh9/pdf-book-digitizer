from __future__ import annotations

from pathlib import Path

from PIL import Image
import pytest

from pdf_book_digitizer.postprocess import (
    OCRRegion,
    extract_footnotes_from_free_ocr,
    normalize_heading,
    parse_ocr_regions,
    postprocess_page,
    reconstruct_paragraphs,
    replace_footnote_markers,
    scale_relative_bbox,
)


@pytest.mark.parametrize(
    ("raw_text", "expected"),
    [
        (
            '第一行\x1b[K\n第二行\n第三段第一行\x1b[4D\x1b[K\n第三段第二行\x1b[10D\x1b[K\n第三段第三行',
            "第一行第二行\n\n第三段第一行第三段第二行第三段第三行",
        ),
        (
            "alpha\nbeta\n\ngamma\x1b[K\ndelta",
            "alpha\n\nbeta\n\ngammadelta",
        ),
    ],
)
def test_reconstruct_paragraphs_uses_escape_sequences_as_join_signals(raw_text: str, expected: str) -> None:
    assert reconstruct_paragraphs(raw_text) == expected


@pytest.mark.parametrize(
    ("text", "level", "expected"),
    [
        ("Already plain subtitle", 2, "## Already plain subtitle"),
        ("## Existing subtitle", 2, "## Existing subtitle"),
        ("# Existing title", 1, "# Existing title"),
    ],
)
def test_normalize_heading_enforces_expected_markdown_heading(text: str, level: int, expected: str) -> None:
    assert normalize_heading(text, level=level) == expected


def test_parse_ocr_regions_reads_tagged_blocks() -> None:
    raw_markdown = (
        "<|ref|>text<|/ref|><|det|>[[1, 2, 3, 4]]<|/det|>\n"
        "alpha\n\n"
        "<|ref|>image<|/ref|><|det|>[[10, 20, 30, 40]]<|/det|>\n"
        "<|ref|>sub_title<|/ref|><|det|>[[50, 60, 70, 80]]<|/det|>\n"
        "subtitle\n"
    )

    assert parse_ocr_regions(raw_markdown) == [
        OCRRegion(ref_type="text", bbox=(1, 2, 3, 4), content="alpha"),
        OCRRegion(ref_type="image", bbox=(10, 20, 30, 40), content=""),
        OCRRegion(ref_type="sub_title", bbox=(50, 60, 70, 80), content="subtitle"),
    ]


def test_postprocess_page_extracts_images_and_preserves_position(tmp_path: Path) -> None:
    page_image_path = tmp_path / "page-0001.jpg"
    figures_dir = tmp_path / "figures"

    image = Image.new("RGB", (100, 100), color="white")
    for x in range(10, 60):
        for y in range(20, 70):
            image.putpixel((x, y), (255, 0, 0))
    image.save(page_image_path, format="JPEG")

    raw_markdown = (
        "<|ref|>text<|/ref|><|det|>[[0, 0, 1000, 100]]<|/det|>\n"
        "前文\n\n"
        "<|ref|>image<|/ref|><|det|>[[100, 200, 600, 700]]<|/det|>\n"
        "<|ref|>image_caption<|/ref|><|det|>[[100, 710, 500, 760]]<|/det|>\n"
        "<center>图一说明</center>\n\n"
        "<|ref|>text<|/ref|><|det|>[[0, 800, 1000, 900]]<|/det|>\n"
        "后文\n"
    )

    processed = postprocess_page(
        raw_markdown=raw_markdown,
        page_image_path=page_image_path,
        output_stem="page-0001",
        figures_dir=figures_dir,
        figure_href_prefix="../figures/",
    )

    figure_path = figures_dir / "page-0001-fig-001.jpg"
    assert processed.markdown == "前文\n\n![](../figures/page-0001-fig-001.jpg)\n\n图一说明\n\n后文"
    assert processed.figure_paths == [figure_path]
    assert figure_path.exists()
    with Image.open(figure_path) as cropped:
        assert cropped.size == (50, 50)


def test_postprocess_page_reruns_free_ocr_for_footnotes(tmp_path: Path) -> None:
    page_image_path = tmp_path / "page-0002.jpg"
    Image.new("RGB", (50, 50), color="white").save(page_image_path, format="JPEG")

    class FakeOCRClient:
        def free_ocr_page_text(self, image_path: Path) -> str:
            assert image_path == page_image_path
            return "① 第一条注释\n② 第二条注释"

    raw_markdown = (
        "<|ref|>text<|/ref|><|det|>[[0, 0, 1000, 1000]]<|/det|>\n"
        "正文①还有②脚注\n"
    )

    processed = postprocess_page(
        raw_markdown=raw_markdown,
        page_image_path=page_image_path,
        output_stem="page-0002",
        figures_dir=tmp_path / "figures",
        figure_href_prefix="../figures/",
        ocr_client=FakeOCRClient(),
    )

    assert processed.markdown == (
        "正文[^1]还有[^2]脚注\n\n[^1]: 第一条注释\n[^2]: 第二条注释"
    )


@pytest.mark.parametrize(
    ("free_ocr_text", "expected"),
    [
        ("① 注释甲\n② 注释乙", {"①": "注释甲", "②": "注释乙"}),
        ("① first note ② second note", {"①": "first note", "②": "second note"}),
    ],
)
def test_extract_footnotes_from_free_ocr(free_ocr_text: str, expected: dict[str, str]) -> None:
    assert extract_footnotes_from_free_ocr(free_ocr_text) == expected


def test_replace_footnote_markers_converts_circled_digits() -> None:
    assert replace_footnote_markers("甲①乙②") == "甲[^1]乙[^2]"


def test_scale_relative_bbox_maps_coordinates_to_pixels() -> None:
    assert scale_relative_bbox((100, 200, 600, 700), width=100, height=200) == (10, 40, 60, 140)
