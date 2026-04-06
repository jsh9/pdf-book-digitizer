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

This tool exposes five command-line endpoints:

- `digitize-book`: render a PDF into page images, OCR the pages, run cleanup/refix passes, and assemble `book.md` plus `book.html`
- `digitize-images`: OCR an existing folder of page images, run cleanup/refix passes, and assemble `book.md` plus `book.html`
- `extract-pdf-pages`: only extract one JPG per PDF page, without OCR
- `fix-raw-ocr-results`: run the cleanup/refix stage on existing `ocr/raw` page artifacts and rebuild `book.md` plus `book.html`
- `inspect-ocr-pages`: open a local browser editor for page images and per-page OCR Markdown

## Run

`digitize-book`

```bash
digitize-book /path/to/book.pdf \
  --output-dir output \
  --model glm-ocr \
  --language-hint "English"
```

If your local Ollama model name is not literally `glm-ocr`, pass the exact installed model tag with `--model`.
For `digitize-book`, `--output-dir` is the parent output folder. The command creates and writes OCR artifacts under `OUTPUT_DIR/ocr/`.

`digitize-images`

```bash
digitize-images /path/to/page-images \
  --output-dir output \
  --model glm-ocr
```

When using `digitize-images`, the per-page OCR output filenames match the input image filenames. For example, `001-cover.jpg` becomes `ocr/raw/001-cover.md` and `ocr/fixed/001-cover.md` by default, or `.json` files with `--output-json`.
For `digitize-images`, `--output-dir` is also the parent output folder. The command writes OCR artifacts under `OUTPUT_DIR/ocr/`, and reruns look for existing files there.
When the image filename contains a trailing number such as `page-0026.jpg`, that number is also used as the displayed page number in `book.md` and `book.html`.
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

`fix-raw-ocr-results`

```bash
fix-raw-ocr-results output
```

This reads existing per-page raw OCR artifacts from `output/ocr/raw/`, sends each page body through the cleanup model, rewrites `output/ocr/fixed/` and `output/ocr/diff/`, runs the same hard-line-break recheck pass used by the main OCR pipeline, and rebuilds `output/book.md` plus `output/book.html`.

`inspect-ocr-pages`

```bash
inspect-ocr-pages \
  --images-dir /path/to/pages \
  --markdown-dir /path/to/output/ocr/fixed
```

This starts a local browser-based editor that shows one page image beside its matching Markdown file, matched by filename stem such as `page-0001.jpg` and `page-0001.md`.

Editor behavior:

- the page image is shown on the left and the Markdown is shown in an editable text area on the right
- the image panel starts sized to show the page image at browser-height scale and can be widened or narrowed by dragging its right edge
- `Save` writes the edited Markdown to a sibling folder named `manually-fixed/`
- `Cmd+S` on macOS, or `Ctrl+S` elsewhere, triggers `Save`
- `Previous Page` moves to the previous page without writing any files
- `Next Page Without Saving` advances to the next page without writing any files
- `Save & Next` saves first and then advances to the next page
- `Cmd+Shift+PageUp` on macOS, or `Ctrl+Shift+PageUp` elsewhere, triggers `Previous Page`
- `Cmd+Shift+PageDown` on macOS, or `Ctrl+Shift+PageDown` elsewhere, triggers `Next Page Without Saving`
- `Cmd+Shift+Enter` on macOS, or `Ctrl+Shift+Enter` elsewhere, triggers `Next Page`
- `End of page is end of paragraph` is a page-level toggle, off by default
- `Hard page break` is a page-level toggle, off by default
- `Cmd+Shift+P` on macOS, or `Ctrl+Shift+P` elsewhere, toggles `End of page is end of paragraph`
- `Cmd+Shift+L` on macOS, or `Ctrl+Shift+L` elsewhere, toggles `Hard page break`
- `Jump to` uses the numeric page index parsed from the filename stem, such as `26` for `page-0026.jpg`
- `Go to next uninspected page` jumps to the next page that has not yet been manually inspected, using the same resumability logic as startup
- `Mark end of chapter` toggles the current page as a chapter-ending page and saves that marker immediately
- chapter-ending pages are saved to `chapter-end-pages.json` in the parent folder of the provided Markdown directory
- end-of-page paragraph flags are saved to `end-of-page-is-end-of-paragraph.json` in the parent folder of the provided Markdown directory
- hard page break flags are saved to `hard-page-break.json` in the parent folder of the provided Markdown directory and pre-populated to `false` for every page when the inspector starts
- diffs between the original Markdown and the edited Markdown are written to a sibling folder named `manually-fixed-diffs/`
- if both `manually-fixed/` and `manually-fixed-diffs/` already exist and contain the same page stems, the editor starts on the first page that has not yet been manually inspected

Example output layout after using the editor:

```text
output/
  ocr/
    chapter-end-pages.json
    end-of-page-is-end-of-paragraph.json
    hard-page-break.json
    fixed/
      page-0001.md
    manually-fixed/
      page-0001.md
    manually-fixed-diffs/
      page-0001.diff
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
