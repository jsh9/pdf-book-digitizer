from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class DigitizerConfig:
    input_pdf: Path
    output_dir: Path
    model: str = "glm-ocr"
    dpi: int = 300
    image_min_width_ratio: float = 0.12
    image_min_height_ratio: float = 0.08
    language_hint: str = ""
    unwrap_text: bool = True
    output_json: bool = False
    llm_refix: bool = True
