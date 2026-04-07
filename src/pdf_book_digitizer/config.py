from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class DigitizerConfig:
    input_pdf: Path
    output_dir: Path
    dpi: int = 300
