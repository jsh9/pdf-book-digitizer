from __future__ import annotations

import re

from ollama import ResponseError, chat


FIX_MODEL = "qwen3.5:9b"
MAX_FIX_ATTEMPTS = 3
ANSI_ESCAPE_CODE_PATTERN = re.compile(r"\x1B\[[0-9;]*[JKmsu]")

FIX_PROMPT = """You are cleaning OCR text from a scanned book page.

Task:
- Remove unwanted trailing garbage characters that appear at the end of apparent lines.
  Typical garbage includes a trailing space or the ANSI fragment \\u001b[K
- These unwanted characters usually appear where a printed line ended on the page, but the paragraph continues.
- Keep the original wording, spelling, punctuation, and paragraph structure.
- "Unwrap" hard-wrapped lines by joining them together, but keep two line breaks between paragraphs.
  (How to "unwrap": if a line break appears to be mid-sentence, join the lines together. 
  If it's western languague, add a space when joining. If it's Chinese/Japanese/Korean, do not add a space.)
- Do not summarize.
- Do not rewrite for style.
- Do not add commentary.
- Output only the cleaned text.
- DO NOT hallucinate any content that isn't present in the original text, even if 
  the original text is garbled or contains obvious OCR errors, or even if the last
  or the first word/character is not a complete word

Input OCR text (after the dashes):
-----
{text}
"""


def fix_ocr_text_with_LLM(text: str, model: str = FIX_MODEL) -> str:
    cleaned_input_text = strip_ansi_escape_codes(text)
    prompt = FIX_PROMPT.format(text=cleaned_input_text)
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

    fixed_text = _strip_code_fences(response.message.content.strip())
    return fixed_text


def strip_ansi_escape_codes(text: str) -> str:
    return ANSI_ESCAPE_CODE_PATTERN.sub("", text)


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 2:
            return "\n".join(lines[1:-1]).strip()
    return stripped
