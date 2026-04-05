from __future__ import annotations

import json
from pathlib import Path

from pdf_book_digitizer.assemble import read_page_json, read_page_markdown, write_page_json
from pdf_book_digitizer.models import PageContent
from pdf_book_digitizer.pipeline import fix_raw_ocr_results


def test_fix_raw_ocr_results_updates_markdown_outputs(tmp_path: Path, monkeypatch) -> None:
    output_dir = tmp_path / "output"
    raw_dir = output_dir / "ocr" / "raw"
    raw_dir.mkdir(parents=True)
    (raw_dir / "001-cover.md").write_text("Header: Intro\n\nalpha\nbeta\n", encoding="utf-8")
    (raw_dir / "leaf.md").write_text("gamma\ndelta\n", encoding="utf-8")

    monkeypatch.setattr(
        "pdf_book_digitizer.pipeline.fix_ocr_text_with_LLM",
        lambda text, model="qwen3.5:9b": text.strip().upper(),
    )
    monkeypatch.setattr("pdf_book_digitizer.pipeline.needs_hard_line_break_fix", lambda lines: False)

    fix_raw_ocr_results(output_dir)

    first_fixed = read_page_markdown(output_dir / "ocr" / "fixed" / "001-cover.md", page_number=1)
    second_fixed = read_page_markdown(output_dir / "ocr" / "fixed" / "leaf.md", page_number=2)

    assert first_fixed.running_header == "Intro"
    assert first_fixed.body_markdown == "ALPHA BETA"
    assert second_fixed.body_markdown == "GAMMA DELTA"
    assert (output_dir / "ocr" / "diff" / "001-cover.diff").exists()
    assert not (output_dir / "ocr" / "diff" / "leaf-2.diff").exists()

    book_markdown = (output_dir / "book.md").read_text(encoding="utf-8")
    assert "## Page 1" in book_markdown
    assert "ALPHA BETA" in book_markdown
    assert "## Page 2" in book_markdown
    assert "GAMMA DELTA" in book_markdown


def test_fix_raw_ocr_results_updates_json_outputs_and_reruns_flagged_pages(tmp_path: Path, monkeypatch) -> None:
    output_dir = tmp_path / "output"
    raw_dir = output_dir / "ocr" / "raw"
    raw_dir.mkdir(parents=True)
    write_page_json(
        PageContent(page_number=7, body_markdown="alpha\nbeta", running_footer="Footer text"),
        raw_dir / "page-0007.json",
    )

    def fake_fix_ocr_text_with_LLM(text: str, model: str = "qwen3.5:9b") -> str:
        if text == "alpha\nbeta":
            return "alpha beta"
        if text == "alpha beta":
            return "ALPHA BETA"
        return text

    monkeypatch.setattr("pdf_book_digitizer.pipeline.fix_ocr_text_with_LLM", fake_fix_ocr_text_with_LLM)
    monkeypatch.setattr(
        "pdf_book_digitizer.pipeline.needs_hard_line_break_fix",
        lambda lines: lines == ["alpha beta"],
    )

    fix_raw_ocr_results(output_dir, unwrap_text=False)

    fixed_page = read_page_json(output_dir / "ocr" / "fixed" / "page-0007.json")
    assert fixed_page.page_number == 7
    assert fixed_page.running_footer == "Footer text"
    assert fixed_page.body_markdown == "ALPHA BETA"

    assert (output_dir / "ocr" / "diff" / "page-0007.diff").exists()
    assert (output_dir / "ocr" / "diff" / "page-0007-2.diff").exists()

    book_html = (output_dir / "book.html").read_text(encoding="utf-8")
    assert "Page 7" in book_html
    assert "ALPHA BETA" in book_html

    payload = json.loads((output_dir / "ocr" / "fixed" / "page-0007.json").read_text(encoding="utf-8"))
    assert payload["running_footer"] == "Footer text"


def test_fix_raw_ocr_results_keeps_unwrapped_fixed_output_after_rerun(tmp_path: Path, monkeypatch) -> None:
    output_dir = tmp_path / "output"
    raw_dir = output_dir / "ocr" / "raw"
    raw_dir.mkdir(parents=True)
    (raw_dir / "page-0001.md").write_text("alpha\nbeta\n", encoding="utf-8")

    def fake_fix_ocr_text_with_LLM(text: str, model: str = "qwen3.5:9b") -> str:
        if text == "alpha\nbeta":
            return "alpha beta"
        if text == "alpha beta":
            return "ALPHA\nBETA"
        return text

    monkeypatch.setattr("pdf_book_digitizer.pipeline.fix_ocr_text_with_LLM", fake_fix_ocr_text_with_LLM)
    monkeypatch.setattr(
        "pdf_book_digitizer.pipeline.needs_hard_line_break_fix",
        lambda lines: lines == ["alpha beta"],
    )

    fix_raw_ocr_results(output_dir, unwrap_text=True)

    fixed_page = read_page_markdown(output_dir / "ocr" / "fixed" / "page-0001.md", page_number=1)
    assert fixed_page.body_markdown == "ALPHA BETA"

    rerun_diff = (output_dir / "ocr" / "diff" / "page-0001-2.diff").read_text(encoding="utf-8")
    assert "ALPHA BETA" in rerun_diff
