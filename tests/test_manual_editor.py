from __future__ import annotations

from pathlib import Path
import json

import pytest

from pdf_book_digitizer.manual_editor import ManualEditorState, build_editor_pages


def write_text(path: Path, content: str = "sample\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def touch_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()


@pytest.mark.parametrize(
    ("image_names", "expected_numbers_by_stem"),
    [
        (
            ["page-0025.jpg", "page-0026.jpg", "page-0100.jpg"],
            {"page-0025": 25, "page-0026": 26, "page-0100": 100},
        ),
        (
            ["001-cover.jpg", "scan_12.png", "leaf.webp"],
            {"001-cover": 1, "scan_12": 12, "leaf": 2},
        ),
    ],
)
def test_build_editor_pages_infers_page_numbers(
    tmp_path: Path,
    image_names: list[str],
    expected_numbers_by_stem: dict[str, int],
) -> None:
    images_dir = tmp_path / "pages"
    markdown_dir = tmp_path / "ocr" / "fixed"
    manual_dir = tmp_path / "ocr" / "manually-fixed"
    diff_dir = tmp_path / "ocr" / "manually-fixed-diffs"

    for image_name in image_names:
        touch_file(images_dir / image_name)
        write_text(markdown_dir / f"{Path(image_name).stem}.md")

    pages = build_editor_pages(images_dir, markdown_dir, manual_dir, diff_dir)

    assert {page.stem: page.page_number for page in pages} == expected_numbers_by_stem


@pytest.mark.parametrize(
    ("manual_stems", "diff_stems", "expected_index", "expected_page_number"),
    [
        ([], [], 0, 25),
        (["page-0025"], ["page-0025"], 1, 26),
        (["page-0025", "page-0026"], ["page-0025", "page-0026"], 2, 27),
        (["page-0025"], [], 0, 25),
        (["page-0025"], ["page-0026"], 0, 25),
        (["page-0025", "page-0026", "page-0027"], ["page-0025", "page-0026", "page-0027"], 2, 27),
    ],
)
def test_manual_editor_state_finds_resume_page(
    tmp_path: Path,
    manual_stems: list[str],
    diff_stems: list[str],
    expected_index: int,
    expected_page_number: int,
) -> None:
    images_dir = tmp_path / "pages"
    markdown_dir = tmp_path / "ocr" / "fixed"
    manual_dir = tmp_path / "ocr" / "manually-fixed"
    diff_dir = tmp_path / "ocr" / "manually-fixed-diffs"

    for stem, content in [("page-0025", "a\n"), ("page-0026", "b\n"), ("page-0027", "c\n")]:
        touch_file(images_dir / f"{stem}.jpg")
        write_text(markdown_dir / f"{stem}.md", content)

    for stem in manual_stems:
        write_text(manual_dir / f"{stem}.md", f"{stem} fixed\n")

    for stem in diff_stems:
        write_text(diff_dir / f"{stem}.diff", f"{stem} diff\n")

    state = ManualEditorState(images_dir, markdown_dir)

    assert state.start_index == expected_index
    assert state.build_page_payload(state.start_index)["pageNumber"] == expected_page_number


@pytest.mark.parametrize(
    ("payload", "expected_by_stem"),
    [
        ({}, {"page-0025": False, "page-0026": False}),
        ({"page-0025": True}, {"page-0025": True, "page-0026": False}),
        ({"page-0025": False, "page-0026": True}, {"page-0025": False, "page-0026": True}),
    ],
)
def test_manual_editor_state_loads_end_of_page_paragraph_flags(
    tmp_path: Path,
    payload: dict[str, bool],
    expected_by_stem: dict[str, bool],
) -> None:
    images_dir = tmp_path / "pages"
    markdown_dir = tmp_path / "ocr" / "fixed"
    toggle_file = tmp_path / "ocr" / "end-of-page-is-end-of-paragraph.json"

    for stem in ["page-0025", "page-0026"]:
        touch_file(images_dir / f"{stem}.jpg")
        write_text(markdown_dir / f"{stem}.md", f"{stem}\n")

    write_text(toggle_file, json.dumps(payload, indent=2) + "\n")

    state = ManualEditorState(images_dir, markdown_dir)

    assert {
        page.stem: state.build_page_payload(page.index)["endOfPageIsEndOfParagraph"]
        for page in state.pages
    } == expected_by_stem


@pytest.mark.parametrize(
    ("updates", "expected_payload"),
    [
        ([(0, True)], {"page-0025": True, "page-0026": False}),
        ([(0, True), (1, False)], {"page-0025": True, "page-0026": False}),
        ([(1, True), (0, False)], {"page-0025": False, "page-0026": True}),
    ],
)
def test_manual_editor_state_persists_end_of_page_paragraph_flags(
    tmp_path: Path,
    updates: list[tuple[int, bool]],
    expected_payload: dict[str, bool],
) -> None:
    images_dir = tmp_path / "pages"
    markdown_dir = tmp_path / "ocr" / "fixed"
    toggle_file = tmp_path / "ocr" / "end-of-page-is-end-of-paragraph.json"

    for stem in ["page-0025", "page-0026"]:
        touch_file(images_dir / f"{stem}.jpg")
        write_text(markdown_dir / f"{stem}.md", f"{stem}\n")

    state = ManualEditorState(images_dir, markdown_dir)

    for index, value in updates:
        state.set_end_of_page_paragraph(index, value)

    assert json.loads(toggle_file.read_text(encoding="utf-8")) == expected_payload


@pytest.mark.parametrize(
    ("payload", "expected_by_stem"),
    [
        ({}, {"page-0025": False, "page-0026": False}),
        ({"page-0025": True}, {"page-0025": True, "page-0026": False}),
        ({"page-0025": False, "page-0026": True}, {"page-0025": False, "page-0026": True}),
    ],
)
def test_manual_editor_state_loads_hard_page_break_flags(
    tmp_path: Path,
    payload: dict[str, bool],
    expected_by_stem: dict[str, bool],
) -> None:
    images_dir = tmp_path / "pages"
    markdown_dir = tmp_path / "ocr" / "fixed"
    toggle_file = tmp_path / "ocr" / "hard-page-break.json"

    for stem in ["page-0025", "page-0026"]:
        touch_file(images_dir / f"{stem}.jpg")
        write_text(markdown_dir / f"{stem}.md", f"{stem}\n")

    write_text(toggle_file, json.dumps(payload, indent=2) + "\n")

    state = ManualEditorState(images_dir, markdown_dir)

    assert {
        page.stem: state.build_page_payload(page.index)["hardPageBreak"]
        for page in state.pages
    } == expected_by_stem


@pytest.mark.parametrize(
    ("updates", "expected_payload"),
    [
        ([(0, True)], {"page-0025": True, "page-0026": False}),
        ([(0, True), (1, False)], {"page-0025": True, "page-0026": False}),
        ([(1, True), (0, False)], {"page-0025": False, "page-0026": True}),
    ],
)
def test_manual_editor_state_persists_hard_page_break_flags(
    tmp_path: Path,
    updates: list[tuple[int, bool]],
    expected_payload: dict[str, bool],
) -> None:
    images_dir = tmp_path / "pages"
    markdown_dir = tmp_path / "ocr" / "fixed"
    toggle_file = tmp_path / "ocr" / "hard-page-break.json"

    for stem in ["page-0025", "page-0026"]:
        touch_file(images_dir / f"{stem}.jpg")
        write_text(markdown_dir / f"{stem}.md", f"{stem}\n")

    state = ManualEditorState(images_dir, markdown_dir)

    for index, value in updates:
        state.set_hard_page_break(index, value)

    assert json.loads(toggle_file.read_text(encoding="utf-8")) == expected_payload


def test_manual_editor_state_prepopulates_hard_page_break_file_on_startup(tmp_path: Path) -> None:
    images_dir = tmp_path / "pages"
    markdown_dir = tmp_path / "ocr" / "fixed"
    toggle_file = tmp_path / "ocr" / "hard-page-break.json"

    for stem in ["page-0025", "page-0026"]:
        touch_file(images_dir / f"{stem}.jpg")
        write_text(markdown_dir / f"{stem}.md", f"{stem}\n")

    ManualEditorState(images_dir, markdown_dir)

    assert json.loads(toggle_file.read_text(encoding="utf-8")) == {
        "page-0025": False,
        "page-0026": False,
    }


@pytest.mark.parametrize(
    ("paragraph_initial", "hard_break_value", "expected_paragraph"),
    [
        (False, True, True),
        (True, True, True),
        (False, False, False),
    ],
)
def test_hard_page_break_turning_on_sets_end_of_page_paragraph(
    tmp_path: Path,
    paragraph_initial: bool,
    hard_break_value: bool,
    expected_paragraph: bool,
) -> None:
    images_dir = tmp_path / "pages"
    markdown_dir = tmp_path / "ocr" / "fixed"
    paragraph_file = tmp_path / "ocr" / "end-of-page-is-end-of-paragraph.json"

    touch_file(images_dir / "page-0025.jpg")
    write_text(markdown_dir / "page-0025.md", "page-0025\n")

    state = ManualEditorState(images_dir, markdown_dir)
    state.set_end_of_page_paragraph(0, paragraph_initial)
    payload = state.set_hard_page_break(0, hard_break_value)

    assert payload["hardPageBreak"] is hard_break_value
    assert payload["endOfPageIsEndOfParagraph"] is expected_paragraph
    assert json.loads(paragraph_file.read_text(encoding="utf-8")) == {"page-0025": expected_paragraph}


def test_end_of_page_paragraph_can_be_manually_turned_off_after_hard_page_break(tmp_path: Path) -> None:
    images_dir = tmp_path / "pages"
    markdown_dir = tmp_path / "ocr" / "fixed"

    touch_file(images_dir / "page-0025.jpg")
    write_text(markdown_dir / "page-0025.md", "page-0025\n")

    state = ManualEditorState(images_dir, markdown_dir)
    state.set_hard_page_break(0, True)
    payload = state.set_end_of_page_paragraph(0, False)

    assert payload["hardPageBreak"] is True
    assert payload["endOfPageIsEndOfParagraph"] is False


@pytest.mark.parametrize(
    ("manual_stems", "diff_stems", "start_after", "expected_index"),
    [
        ([], [], 0, 1),
        (["page-0025"], ["page-0025"], 0, 1),
        (["page-0025", "page-0026"], ["page-0025", "page-0026"], 0, 2),
        (["page-0025", "page-0026", "page-0027"], ["page-0025", "page-0026", "page-0027"], 1, 1),
        (["page-0025"], [], 0, 1),
    ],
)
def test_manual_editor_state_finds_next_uninspected_page(
    tmp_path: Path,
    manual_stems: list[str],
    diff_stems: list[str],
    start_after: int,
    expected_index: int,
) -> None:
    images_dir = tmp_path / "pages"
    markdown_dir = tmp_path / "ocr" / "fixed"
    manual_dir = tmp_path / "ocr" / "manually-fixed"
    diff_dir = tmp_path / "ocr" / "manually-fixed-diffs"

    for stem in ["page-0025", "page-0026", "page-0027"]:
        touch_file(images_dir / f"{stem}.jpg")
        write_text(markdown_dir / f"{stem}.md", f"{stem}\n")

    for stem in manual_stems:
        write_text(manual_dir / f"{stem}.md", f"{stem} fixed\n")

    for stem in diff_stems:
        write_text(diff_dir / f"{stem}.diff", f"{stem} diff\n")

    state = ManualEditorState(images_dir, markdown_dir)

    assert state.find_next_uninspected_index(start_after) == expected_index
