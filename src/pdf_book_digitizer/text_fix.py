from __future__ import annotations

from ollama import ResponseError, chat


FIX_MODEL = "qwen3.5:9b"

FIX_PROMPT = """You are cleaning OCR text from a scanned book page.

Task:
- Remove unwanted trailing garbage characters that appear at the end of apparent lines.
- Typical garbage includes a trailing space or the ANSI fragment \\u001b[K.
- These unwanted characters usually appear where a printed line ended on the page, but the paragraph continues.
- Keep the original wording, spelling, punctuation, and paragraph structure.
- "Unwrap" hard-wrapped lines by joining them together, but keep single newlines between paragraphs.
- Do not summarize.
- Do not rewrite for style.
- Do not add commentary.
- Output only the cleaned text.

Input OCR text:
<<<OCR_TEXT
{text}
OCR_TEXT
>>>"""


def fix_ocr_text(text: str, model: str = FIX_MODEL) -> str:
    prompt = FIX_PROMPT.format(text=text)
    try:
        response = chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            think=False,
        )
    except ResponseError as exc:
        raise RuntimeError(f"Ollama chat failed for text-fix model {model!r}. {exc.error}") from exc
    except Exception as exc:
        raise RuntimeError(
            "The Ollama Python client failed during the text-fix step. "
            "Ensure Ollama is running and the `ollama` Python package is installed."
        ) from exc
    return _strip_code_fences(response.message.content.strip())


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 2:
            return "\n".join(lines[1:-1]).strip()
    return stripped
