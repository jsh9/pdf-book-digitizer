from __future__ import annotations

from pathlib import Path

from PIL import Image

from pdf_book_digitizer.models import BoundingBox, PageContent


def crop_page_images(
    page_image_path: Path,
    page_content: PageContent,
    output_dir: Path,
    min_width_ratio: float,
    min_height_ratio: float,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(page_image_path) as page_image:
        width, height = page_image.size
        min_width = max(1, int(width * min_width_ratio))
        min_height = max(1, int(height * min_height_ratio))

        kept_images = []
        for region in page_content.images:
            bbox = region.bbox.clamp(width, height)
            if not _is_valid_bbox(bbox, min_width, min_height):
                continue
            cropped = page_image.crop((bbox.left, bbox.top, bbox.right, bbox.bottom))
            asset_name = f"page-{page_content.page_number:04d}-image-{region.index:02d}.jpg"
            cropped.save(output_dir / asset_name, format="JPEG", quality=95)
            region.asset_name = asset_name
            kept_images.append(region)

        page_content.images = kept_images


def _is_valid_bbox(bbox: BoundingBox, min_width: int, min_height: int) -> bool:
    return bbox.width >= min_width and bbox.height >= min_height
