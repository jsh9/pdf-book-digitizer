from __future__ import annotations

import difflib
from pathlib import Path


def build_unified_diff(before: str, after: str, label: str) -> str:
    before_lines = before.splitlines(keepends=True)
    after_lines = after.splitlines(keepends=True)
    diff_lines = difflib.unified_diff(
        before_lines,
        after_lines,
        fromfile=f"{label}.before",
        tofile=f"{label}.after",
        lineterm="",
    )
    diff_text = "\n".join(diff_lines)
    if diff_text:
        return diff_text + "\n"
    return ""


def write_diff(diff_text: str, output_path: Path) -> None:
    output_path.write_text(diff_text, encoding="utf-8")
