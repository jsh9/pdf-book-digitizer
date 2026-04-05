from __future__ import annotations

from pathlib import Path


SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def collect_image_paths(images_dir: Path) -> list[Path]:
    if not images_dir.exists():
        raise FileNotFoundError(f"Image directory does not exist: {images_dir}")
    if not images_dir.is_dir():
        raise NotADirectoryError(f"Image path is not a directory: {images_dir}")

    image_paths = [
        path for path in sorted(images_dir.iterdir()) if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES
    ]
    if not image_paths:
        raise ValueError(f"No supported image files found in {images_dir}")
    return image_paths
