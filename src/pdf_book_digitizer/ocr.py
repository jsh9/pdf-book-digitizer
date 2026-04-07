from __future__ import annotations

import subprocess
from pathlib import Path

from pdf_book_digitizer.models import PageContent


DEESEEK_OCR_MODEL = "deepseek-ocr"
DEESEEK_OCR_PROMPT = "<|grounding|>Convert the document to markdown."


class OllamaOCRClient:
    def ocr_page(self, image_path: Path, page_number: int) -> PageContent:
        body_text = self._run_ocr(image_path=image_path).strip()
        return PageContent(page_number=page_number, body_markdown=body_text)

    def _run_ocr(self, image_path: Path) -> str:
        command = [
            "ollama",
            "run",
            DEESEEK_OCR_MODEL,
            _build_ocr_input(image_path),
        ]
        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("`ollama` is not installed or not available on PATH.") from exc
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip()
            raise RuntimeError(
                f"`ollama run` failed for model {DEESEEK_OCR_MODEL!r} and image {str(image_path)!r}. {stderr}"
            ) from exc
        return result.stdout.strip()


def _build_ocr_input(image_path: Path) -> str:
    return f"{image_path.resolve()}\n{DEESEEK_OCR_PROMPT}"
