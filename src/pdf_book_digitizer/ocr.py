from __future__ import annotations

import subprocess
from pathlib import Path

from pdf_book_digitizer.models import PageContent


DEESEEK_OCR_MODEL = "deepseek-ocr"
DEESEEK_OCR_PROMPT = "<|grounding|>Convert the document to markdown."
FREE_OCR_PROMPT = "Free OCR."
OCR_TIMEOUT_SECONDS = 120


class OCRTimeoutError(RuntimeError):
    pass


class OllamaOCRClient:
    def ocr_page(self, image_path: Path, page_number: int) -> PageContent:
        body_text = self._run_ocr(image_path=image_path, prompt=DEESEEK_OCR_PROMPT).strip()
        return PageContent(page_number=page_number, body_markdown=body_text)

    def free_ocr_page_text(self, image_path: Path) -> str:
        return self._run_ocr(image_path=image_path, prompt=FREE_OCR_PROMPT).strip()

    def _run_ocr(self, image_path: Path, prompt: str) -> str:
        command = [
            "ollama",
            "run",
            DEESEEK_OCR_MODEL,
            _build_ocr_input(image_path, prompt),
        ]
        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=OCR_TIMEOUT_SECONDS,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("`ollama` is not installed or not available on PATH.") from exc
        except subprocess.TimeoutExpired as exc:
            raise OCRTimeoutError(
                f"`ollama run` timed out after {OCR_TIMEOUT_SECONDS} seconds for image {str(image_path)!r}."
            ) from exc
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip()
            raise RuntimeError(
                f"`ollama run` failed for model {DEESEEK_OCR_MODEL!r} and image {str(image_path)!r}. {stderr}"
            ) from exc
        return result.stdout.strip()


def _build_ocr_input(image_path: Path, prompt: str) -> str:
    return f"{image_path.resolve()}\n{prompt}"
