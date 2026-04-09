from __future__ import annotations

from pathlib import Path

from PIL import Image
import pytest

from pdf_book_digitizer.postprocess import (
    OCRRegion,
    extract_footnotes_from_free_ocr,
    normalize_heading,
    normalize_ocr_text,
    normalize_ocr_test_to_extract_footnote,
    parse_ocr_regions,
    postprocess_page,
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
    assert normalize_ocr_text(raw_text) == expected


def test_normalize_free_ocr_text_for_footnotes_joins_escape_wrapped_lines_but_preserves_real_newlines() -> None:
    free_ocr_text = (
        "正文第一行\x1b[K\n"
        "正文第二行\n\n"
        "① 注释第一行\x1b[K\n"
        "注释续行\n"
        "注释第三行\n\n"
        "② 第二条注释\n"
    )

    assert normalize_ocr_test_to_extract_footnote(free_ocr_text) == (
        "正文第一行正文第二行\n\n① 注释第一行注释续行\n注释第三行\n\n② 第二条注释"
    )


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


def test_postprocess_page_preserves_multiline_footnotes(tmp_path: Path) -> None:
    page_image_path = tmp_path / "page-0003.jpg"
    Image.new("RGB", (50, 50), color="white").save(page_image_path, format="JPEG")

    class FakeOCRClient:
        def free_ocr_page_text(self, image_path: Path) -> str:
            assert image_path == page_image_path
            return "① 第一条注释第一行\n第一条注释第二行\n\n② 第二条注释"

    raw_markdown = (
        "<|ref|>text<|/ref|><|det|>[[0, 0, 1000, 1000]]<|/det|>\n"
        "正文①还有②脚注\n"
    )

    processed = postprocess_page(
        raw_markdown=raw_markdown,
        page_image_path=page_image_path,
        output_stem="page-0003",
        figures_dir=tmp_path / "figures",
        figure_href_prefix="../figures/",
        ocr_client=FakeOCRClient(),
    )

    assert processed.markdown == (
        "正文[^1]还有[^2]脚注\n\n[^1]: 第一条注释第一行\n    第一条注释第二行\n[^2]: 第二条注释"
    )


@pytest.mark.parametrize(
    ("free_ocr_text", "expected"),
    [
        ("① 注释甲\n\n② 注释乙", {"①": "注释甲", "②": "注释乙"}),
        ("① 注释甲\n② 注释乙", {"①": "注释甲", "②": "注释乙"}),
        ("① first note ② second note", {"①": "first note", "②": "second note"}),
        ("① 第一条注释第一行\n第一条注释第二行\n\n② 第二条注释", {"①": "第一条注释第一行\n第一条注释第二行", "②": "第二条注释"}),
        (
            "正文①提到前文，随后又有②插入。\n另一段里再次出现①，但都不是注释。\n\n① 真正的注释甲\n\n② 真正的注释乙",
            {"①": "真正的注释甲", "②": "真正的注释乙"},
        ),
    ],
)
def test_extract_footnotes_from_free_ocr(free_ocr_text: str, expected: dict[str, str]) -> None:
    assert extract_footnotes_from_free_ocr(free_ocr_text) == expected


def test_extract_footnotes_from_prepared_shuihu_fixture() -> None:
    normalized_text = Path("tests/test_data/水浒传_extract_footnote/normalized.md").read_text(encoding="utf-8")

    assert extract_footnotes_from_free_ocr(normalized_text) == {
        "①": "饿文——就是“饿纹”。迷信的说法：人脸上的皱纹，如果延长伸进嘴里，这人后来定要饿死。因此，称伸进嘴里的皱纹叫做饿纹。",
        "②": "一佛出世——常与“二佛涅槃”（和尚死了，佛教称为圆寂，或称涅槃、灭度）或“二佛生天”连用。是死去活来的意思。",
    }


def test_replace_footnote_markers_converts_circled_digits() -> None:
    assert replace_footnote_markers("甲①乙②") == "甲[^1]乙[^2]"


def test_scale_relative_bbox_maps_coordinates_to_pixels() -> None:
    assert scale_relative_bbox((100, 200, 600, 700), width=100, height=200) == (10, 40, 60, 140)


def test_postprocess_page_matches_pride_and_prejudice_ground_truth(tmp_path: Path) -> None:
    fixture_root = Path("tests/test_data/pride_and_prejudice")
    raw_markdown = (fixture_root / "ocr" / "raw" / "page0001.md").read_text(encoding="utf-8")
    page_image_path = fixture_root / "pages" / "page0001.jpg"
    expected_markdown_path = fixture_root / "ocr_ground_truth" / "new" / "page0001.md"
    expected_figure_path = fixture_root / "ocr_ground_truth" / "figures" / "page0001-fig-001.jpg"

    processed = postprocess_page(
        raw_markdown=raw_markdown,
        page_image_path=page_image_path,
        output_stem="page0001",
        figures_dir=tmp_path / "figures",
        figure_href_prefix="../figures/",
    )

    generated_figure_path = tmp_path / "figures" / "page0001-fig-001.jpg"

    assert processed.markdown == expected_markdown_path.read_text(encoding="utf-8").strip()
    assert processed.figure_paths == [generated_figure_path]
    assert generated_figure_path.exists()
    assert_images_equal_rgb(generated_figure_path, expected_figure_path)


def test_postprocess_page_matches_shuihu_ground_truth_with_mocked_free_ocr(tmp_path: Path) -> None:
    fixture_root = Path("tests/test_data/水浒传")
    raw_markdown = (fixture_root / "ocr" / "raw" / "page-0001.md").read_text(encoding="utf-8")
    page_image_path = fixture_root / "pages" / "page-0001.jpg"
    expected_markdown_path = fixture_root / "ocr_ground_truth" / "new" / "page-0001.md"
    mocked_free_ocr_output = Path("tests/test_data/水浒传_extract_footnote/free_ocr_page_text_out.md").read_text(
        encoding="utf-8"
    )

    class FakeOCRClient:
        def free_ocr_page_text(self, image_path: Path) -> str:
            assert image_path == page_image_path
            return mocked_free_ocr_output

    expected_footnotes = (
        "[^1]: 饿文——就是“饿纹”。迷信的说法：人脸上的皱纹，如果延长伸进嘴里，这人后来定要饿死。因此，称伸进嘴里的皱纹叫做饿纹。\n"
        "[^2]: 一佛出世——常与“二佛涅槃”（和尚死了，佛教称为圆寂，或称涅槃、灭度）或“二佛生天”连用。是死去活来的意思。"
    )

    processed = postprocess_page(
        raw_markdown=raw_markdown,
        page_image_path=page_image_path,
        output_stem="page-0001",
        figures_dir=tmp_path / "figures",
        figure_href_prefix="../figures/",
        ocr_client=FakeOCRClient(),
    )

    expected_body, _ = expected_markdown_path.read_text(encoding="utf-8").strip().split("\n\n[^1]: ", maxsplit=1)
    actual_body, actual_footnotes = processed.markdown.split("\n\n[^1]: ", maxsplit=1)

    assert actual_body == expected_body
    assert f"[^1]: {actual_footnotes}" == expected_footnotes
    assert processed.figure_paths == []


def assert_images_equal_rgb(actual_path: Path, expected_path: Path) -> None:
    with Image.open(actual_path) as actual_image, Image.open(expected_path) as expected_image:
        actual_rgb = actual_image.convert("RGB")
        expected_rgb = expected_image.convert("RGB")
        assert actual_rgb.size == expected_rgb.size
        assert list(actual_rgb.getdata()) == list(expected_rgb.getdata())
