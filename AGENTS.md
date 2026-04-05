# AGENTS.md

Maintainer notes for `pdf-book-digitizer`.

## Purpose

This project digitizes scanned or poorly OCRed books into:

- page JPGs
- per-page OCR artifacts
- combined `book.md`
- combined `book.html`

Primary user flows:

- `digitize-book`: PDF -> page JPGs -> OCR -> cleanup -> assembly
- `digitize-images`: existing page images -> OCR -> cleanup -> assembly
- `extract-pdf-pages`: PDF -> page JPGs only

## Current Output Layout

Typical output tree:

```text
output/
  book.md
  book.html
  ocr/
    raw/
    fixed/
    diff/
  pages/
```

Per-page OCR artifacts:

- `ocr/raw/`: text immediately after OCR
- `ocr/fixed/`: text after the initial LLM cleanup pass
- `ocr/diff/`: diff between raw and fixed, plus optional `-2` diff from the later hard-line-break re-fix pass

## OCR And Cleanup Pipeline

OCR:

- OCR model is user-selectable via `--model`
- default OCR model is `glm-ocr`
- OCR itself runs through `ollama run`
- documented task form used: `Text Recognition:`

Initial cleanup:

- cleanup model is currently `qwen3.5:9b`
- cleanup runs through the Ollama Python client in `text_fix.py`
- only `response.message.content` is used

Hard-line-break recheck:

- after initial OCR + cleanup, fixed files are scanned with `needs_hard_line_break_fix()`
- if a page is flagged, one additional re-fix pass is run with `qwen3.5:9b`
- that follow-up diff is saved as `<stem>-2.diff`

Unwrapping:

- optional text unwrapping runs after cleanup/refix on the in-memory assembled page content
- this joins hard-wrapped lines inside a paragraph and leaves single newlines between paragraphs

## Important Flags

Shared flags on `digitize-book` and `digitize-images`:

- `--model`: OCR model, default `glm-ocr`
- `--unwrap-text` / `--no-unwrap-text`
- `--output-json`: write per-page artifacts as JSON instead of Markdown
- `--llm-refix` / `--no-llm-refix`: enable or disable all LLM-based cleanup/refix passes

Behavior of `--no-llm-refix`:

- skips the initial cleanup pass
- skips the later hard-line-break re-fix pass
- still writes `raw/`, `fixed/`, and `diff/`
- `fixed/` becomes identical to `raw/`

## Resumability

`digitize-images` is resumable.

A page is skipped if all of these already exist for the image stem:

- `ocr/raw/<stem>.(md|json)`
- `ocr/fixed/<stem>.(md|json)`
- `ocr/diff/<stem>.diff`

When skipped:

- a stdout skip message is printed
- the stored fixed artifact is loaded back into memory so `book.md` and `book.html` can still be assembled

PDF page extraction is also resumable:

- if `pages/page-XXXX.jpg` already exists, extraction is skipped
- a stdout skip message is printed

## Assembly

Combined outputs are assembled from the final in-memory page content:

- `book.md`
- `book.html`

Page-level per-file artifacts are separate from the combined assembled outputs.

## Hard Line Break Heuristic

The current heuristic in `hard_line_breaks.py` is based on "short last line" logic.

Key ideas:

- determine a maximum visible line length
- classify lines near that maximum as "full"
- classify much shorter lines as "short"
- detect `[Full, Full, ..., Short]` block patterns
- support a single-paragraph special case
- reject uniformly short text

Important constraint:

- do not rewrite the existing test cases in `tests/test_hard_line_breaks.py` unless explicitly asked

## Import Style

Use absolute imports throughout the Python package:

- `from pdf_book_digitizer...`

Do not add new relative imports.

## Testing

Current validated checks used in this repo:

```bash
python3 -m compileall src tests
pytest -q tests/test_hard_line_breaks.py
```

There is currently no broader automated test suite beyond the heuristic tests.

## Known Constraints

- figure/image extraction inside OCR pages is not implemented
- `Figure Recognition:` is exposed conceptually but no bounding-box extraction pipeline is active
- headers, footers, and printed page numbers are not reliably separated by OCR yet
- HTML assembly is intentionally simple and page-based

## When Editing

- preserve the artifact layout unless explicitly changing product behavior
- preserve resumability behavior for `digitize-images`
- preserve stdout progress/skip messages unless there is a strong reason to change them
- if changing cleanup/refix sequencing, update both README and this file
