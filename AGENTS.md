# AGENTS.md

Maintainer notes for `pdf-book-digitizer`.

## Purpose

This project digitizes scanned or poorly OCRed books into:

- page JPGs
- per-page raw OCR Markdown files
- per-page post-processed Markdown files
- extracted figure crops

Primary user flows:

- `digitize-book`: PDF -> page JPGs -> OCR Markdown
- `digitize-images`: existing page images -> OCR Markdown
- `extract-pdf-pages`: PDF -> page JPGs only

## Current Output Layout

Typical output tree:

```text
output/
  ocr/
    figures/
      page-0001-fig-001.jpg
    new/
      page-0001.md
    raw/
      page-0001.md
  pages/
    page-0001.jpg
```

Per-page OCR artifacts:

- `ocr/raw/`: raw OCR Markdown returned by DeepSeek OCR
- `ocr/new/`: post-processed Markdown derived from `ocr/raw/`
- `ocr/figures/`: cropped figures extracted from OCR image regions

## OCR Pipeline

OCR:

- OCR always uses Ollama `deepseek-ocr`
- OCR runs through `ollama run`
- prompt form used:

```text
/absolute/path/to/page.jpg
<|grounding|>Convert the document to markdown.
```

- OCR output is treated as final Markdown
- post-processing then:
  - reconstructs paragraphs from terminal/control garbage such as `\x1b[K`
  - removes OCR region tags from pure text blocks
  - normalizes subtitle headings
  - crops image regions into `ocr/figures/`
  - reruns `Free OCR.` when circled footnote markers are detected and appends Markdown footnotes
- there is no JSON OCR output
- there are no combined `book.md` or `book.html` outputs

## Resumability

`digitize-images` is resumable.

A page is skipped if this already exists for the image stem:

- `ocr/raw/<stem>.md`

When skipped:

- a stdout skip message is printed
- post-processing still runs from the stored raw Markdown so `ocr/new/` and `ocr/figures/` stay in sync

PDF page extraction is also resumable:

- if `pages/page-XXXX.jpg` already exists, extraction is skipped
- a stdout skip message is printed

## Import Style

Use absolute imports throughout the Python package:

- `from pdf_book_digitizer...`

Do not add new relative imports.

## Testing

Current validated checks used in this repo:

```bash
python3 -m compileall src tests
pytest -q tests/test_pipeline.py tests/test_ocr.py tests/test_postprocess.py tests/test_manual_editor.py
```

## Known Constraints

- running headers, footers, and printed page numbers are not reliably separated by OCR yet
- the manual inspection editor remains available for reviewing Markdown page files

## When Editing

- preserve the artifact layout unless explicitly changing product behavior
- preserve resumability behavior for `digitize-images`
- preserve stdout progress/skip messages unless there is a strong reason to change them
- if changing OCR behavior or output layout, update both README and this file
