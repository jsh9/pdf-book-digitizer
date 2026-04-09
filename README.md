# pdf-book-digitizer

Pipeline for turning scanned PDFs or existing page images into per-page OCR Markdown.

## What It Does

- `digitize-book`: render a PDF into page JPGs, then OCR each page image into Markdown
- `digitize-images`: OCR an existing folder of page images into Markdown
- `extract-pdf-pages`: extract one JPG per PDF page without OCR
- `inspect-ocr-pages`: open the local inspection editor for page images and Markdown files

OCR is now a single-pass flow using Ollama `deepseek-ocr`. There is no cleanup pass, no refix pass, no JSON output, and no combined `book.md` or `book.html`.

After raw OCR is written, the pipeline also generates a post-processed Markdown page and extracts figure crops from any OCR image regions.

## Output Layout

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

- `ocr/raw/` contains the final OCR Markdown for each page
- `ocr/new/` contains the post-processed Markdown for each page
- `ocr/figures/` contains cropped figure images extracted from OCR image regions
- `pages/` exists when the input was a PDF rendered by `digitize-book`

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## OCR Prompt

Each page image is sent to Ollama in this form:

```bash
ollama run deepseek-ocr "/absolute/path/to/page.jpg
<|grounding|>Convert the document to markdown."
```

## Commands

`digitize-book`

```bash
digitize-book /path/to/book.pdf --output-dir output --dpi 300
```

- renders page images to `output/pages/`
- writes raw OCR Markdown to `output/ocr/raw/`
- writes post-processed Markdown to `output/ocr/new/`
- writes extracted figure crops to `output/ocr/figures/`

`digitize-images`

```bash
digitize-images /path/to/page-images --output-dir output
```

- uses the input image filename stem for the OCR output filename
- example: `001-cover.jpg` becomes `output/ocr/raw/001-cover.md` and `output/ocr/new/001-cover.md`
- reruns are resumable for OCR: if `ocr/raw/<stem>.md` already exists, OCR is skipped and post-processing is rebuilt from the stored raw Markdown

`extract-pdf-pages`

```bash
extract-pdf-pages /path/to/book.pdf --output-dir pages --dpi 300
```

`inspect-ocr-pages`

```bash
inspect-ocr-pages \
  --images-dir /path/to/pages \
  --markdown-dir /path/to/output/ocr/raw
```

This opens the existing local browser editor for reviewing page images beside their Markdown files.

## Notes

- OCR output is written as Markdown only
- post-processing removes OCR region tags for text blocks, reconstructs paragraphs from terminal-control garbage, normalizes subtitle headings, extracts image regions, and adds Markdown footnotes when circled numerals trigger a follow-up `Free OCR.` pass
- PDF page extraction is resumable: if `pages/page-XXXX.jpg` already exists, extraction is skipped
- running headers, footers, and printed page numbers are not reliably separated yet
