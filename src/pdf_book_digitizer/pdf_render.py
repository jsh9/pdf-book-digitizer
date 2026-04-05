from __future__ import annotations

from pathlib import Path

import fitz


def render_pdf_to_jpgs(pdf_path: Path, output_dir: Path, dpi: int) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    image_paths: list[Path] = []
    matrix = fitz.Matrix(dpi / 72.0, dpi / 72.0)

    for page_index in range(doc.page_count):
        out_path = output_dir / f"page-{page_index + 1:04d}.jpg"
        if out_path.exists():
            print(f"Skipping page image extraction for page-{page_index + 1:04d}; found existing {out_path.name}")
            image_paths.append(out_path)
            continue
        page = doc.load_page(page_index)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        pix.save(out_path, output="jpeg", jpg_quality=95)
        image_paths.append(out_path)

    doc.close()
    return image_paths
