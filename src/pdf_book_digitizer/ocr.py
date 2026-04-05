from __future__ import annotations

from pathlib import Path
import subprocess

from pdf_book_digitizer.models import PageContent


class OllamaOCRClient:
    def __init__(self, model: str) -> None:
        self.model = model

    def ocr_page(self, image_path: Path, page_number: int, language_hint: str = "") -> PageContent:
        prompt = _build_text_prompt(language_hint)
        body_text = self._run_task(image_path=image_path, prompt=prompt).strip()
        return PageContent(
            page_number=page_number,
            body_markdown=body_text,
            running_header="",
            running_footer="",
            printed_page_number="",
            images=[],
        )

    def describe_figures(self, image_path: Path) -> str:
        return self._run_task(image_path=image_path, prompt="Figure Recognition:").strip()

    def _run_task(self, image_path: Path, prompt: str) -> str:
        command = [
            "ollama",
            "run",
            self.model,
            f"{prompt} {image_path}",
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
                f"`ollama run` failed for model {self.model!r} and image {str(image_path)!r}. {stderr}"
            ) from exc
        return result.stdout.strip()


def _build_text_prompt(language_hint: str) -> str:
    if language_hint:
        return f"Text Recognition ({language_hint}):"
    return "Text Recognition:"
