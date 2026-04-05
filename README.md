# pdf-book-digitizer

Pipeline for turning scanned or poorly OCRed PDF books into:

- rasterized page images
- per-page OCR Markdown or JSON
- combined `book.md` and `book.html` outputs

It supports two OCR entry paths:

- start from a PDF file
- start from an existing folder of page images

## Why HTML instead of Word or Markdown

Use HTML as the primary intermediate format.

- Calibre ingests HTML very reliably.
- HTML preserves inline images and page-level structure better than Word.
- Markdown is workable, but book OCR usually needs richer control around figures, captions, and cleanup.
- If needed later, the HTML can still be converted into EPUB directly or transformed into Markdown.

The current pipeline therefore emits both `book.md` and `book.html` plus image assets.

## Workflow

1. Render the PDF into one JPG per page.
2. Send each page image to `glm-ocr` using Ollama's documented OCR task prompt:
   - `Text Recognition:`
3. Run a second LLM pass with `qwen3.5:9b` to clean OCR line-end garbage such as trailing spaces or `\u001b[K`.
4. Save the raw OCR text and the fixed OCR text separately.
5. Store a diff for raw versus fixed and print that diff to stdout.
6. Check the files in `ocr/fixed/` for hard line breaks and re-fix flagged pages with `qwen3.5:9b` for 1 additional pass, saving a `-2` diff if needed.
7. Assemble all pages into `book.md` and `book.html`.

By default, OCR text is unwrapped so that hard-wrapped line endings inside a paragraph are joined into spaces, and paragraph breaks are represented by a single newline.
By default, per-page OCR results are written as Markdown files.

The repository also exposes a `Figure Recognition:` helper in code, but it is not currently used to crop images because the official `glm-ocr` usage does not document figure bounding-box output.

## Project layout

```text
output/
  book.md
  book.html
  ocr/
    diff/
      page-0001.diff
      page-0001-2.diff
    fixed/
      page-0001.md
    raw/
      page-0001.md
  pages/
    page-0001.jpg
```

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Endpoints

This tool exposes three command-line endpoints:

- `digitize-book`: render a PDF into page images, OCR the pages, run cleanup/refix passes, and assemble `book.md` plus `book.html`
- `digitize-images`: OCR an existing folder of page images, run cleanup/refix passes, and assemble `book.md` plus `book.html`
- `extract-pdf-pages`: only extract one JPG per PDF page, without OCR

## Run

`digitize-book`

```bash
digitize-book /path/to/book.pdf \
  --output-dir output \
  --model glm-ocr \
  --language-hint "English"
```

If your local Ollama model name is not literally `glm-ocr`, pass the exact installed model tag with `--model`.

`digitize-images`

```bash
digitize-images /path/to/page-images \
  --output-dir output \
  --model glm-ocr
```

When using `digitize-images`, the per-page OCR output filenames match the input image filenames. For example, `001-cover.jpg` becomes `ocr/raw/001-cover.md` and `ocr/fixed/001-cover.md` by default, or `.json` files with `--output-json`.
When rerunning `digitize-images`, a page is skipped if matching files already exist in all three locations: `ocr/raw/`, `ocr/fixed/`, and `ocr/diff/`.
When a page is skipped during OCR or PDF page-image extraction, the pipeline prints a skip message to stdout.

Shared flags for `digitize-book` and `digitize-images`:

```bash
digitize-book /path/to/book.pdf --no-unwrap-text
digitize-images /path/to/page-images --no-unwrap-text
```

Disable all LLM-based refixing passes:

```bash
digitize-book /path/to/book.pdf --no-llm-refix
digitize-images /path/to/page-images --no-llm-refix
```

Write JSON per-page OCR files instead of Markdown:

```bash
digitize-book /path/to/book.pdf --output-json
digitize-images /path/to/page-images --output-json
```

`extract-pdf-pages`

```bash
extract-pdf-pages /path/to/book.pdf \
  --output-dir pages \
  --dpi 300
```

OCR execution shells out to the working CLI form directly:

```bash
ollama run glm-ocr "Text Recognition: ./image.png"
```

The OCR cleanup pass uses the Ollama Python API directly and reads only `response.message.content`:

```python
from ollama import chat

response = chat(
    model="qwen3.5:9b",
    messages=[{"role": "user", "content": "<prompt with OCR text>"}],
)
print(response.message.content)
```

## Notes on OCR quality

- The current implementation uses `ollama run` directly because that is the path verified to work with `glm-ocr`.
- After OCR, each page text is sent through `qwen3.5:9b` to remove line-end garbage from the OCR output.
- The raw OCR text is written to `ocr/raw/` and the fixed text is written to `ocr/fixed/`, using Markdown by default or JSON with `--output-json`.
- The raw-vs-fixed diff is written to `ocr/diff/` and also printed to stdout during processing.
- Before assembling `book.html`, the pipeline checks `ocr/fixed/` for hard line breaks using a line-length heuristic and may send flagged pages through `qwen3.5:9b` 1 more time, producing a `-2` diff.
- After the cleanup passes, the pipeline assembles both `book.md` and `book.html` from the final page content.
- Use `--no-llm-refix` to skip both the initial LLM cleanup pass and the later hard-line-break re-fix pass.
- `digitize-images` is resumable: if a page already has matching raw, fixed, and diff artifacts, that page is skipped on the next run.
- PDF page-image extraction is also resumable: if `pages/page-XXXX.jpg` already exists, that page image is skipped and a message is printed to stdout.
- Text unwrapping is enabled by default. It converts single line breaks within a paragraph into spaces and converts paragraph breaks to single newlines.
- Per-page OCR files are written as Markdown by default. Use `--output-json` to switch to JSON.
- Running headers, footers, and printed page numbers are not yet separated into dedicated fields. `glm-ocr` is currently used as raw text OCR.
- Figure cropping is not implemented because the official `Figure Recognition:` usage does not specify coordinate output.
- The assembled HTML keeps OCR text inside `<pre>` blocks to preserve model output faithfully. A later cleanup pass can convert this into more semantic chapter HTML.

## Likely next improvements

- chapter detection and TOC generation
- post-OCR cleanup and de-hyphenation
- add a dedicated page-image detection step that returns crop coordinates
- better figure/caption placement in final HTML
- direct EPUB packaging instead of relying on a later Calibre step
