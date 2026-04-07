# pdf-book-digitizer

Pipeline for turning scanned PDFs or existing page images into per-page OCR Markdown.

## What It Does

- `digitize-book`: render a PDF into page JPGs, then OCR each page image into Markdown
- `digitize-images`: OCR an existing folder of page images into Markdown
- `extract-pdf-pages`: extract one JPG per PDF page without OCR
- `inspect-ocr-pages`: open the local inspection editor for page images and Markdown files

OCR is now a single-pass flow using Ollama `deepseek-ocr`. There is no cleanup pass, no refix pass, no JSON output, and no combined `book.md` or `book.html`.

## Output Layout

```text
output/
  ocr/
    raw/
      page-0001.md
  pages/
    page-0001.jpg
```

- `ocr/raw/` contains the final OCR Markdown for each page
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
- writes OCR Markdown to `output/ocr/raw/`

`digitize-images`

```bash
digitize-images /path/to/page-images --output-dir output
```

- uses the input image filename stem for the OCR output filename
- example: `001-cover.jpg` becomes `output/ocr/raw/001-cover.md`
- reruns are resumable: if `ocr/raw/<stem>.md` already exists, that page is skipped

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
- PDF page extraction is resumable: if `pages/page-XXXX.jpg` already exists, extraction is skipped
- figure extraction inside OCR pages is not implemented
- running headers, footers, and printed page numbers are not reliably separated yet
