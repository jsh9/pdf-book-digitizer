from __future__ import annotations


FULL_LINE_RATIO = 0.85
SHORT_LINE_RATIO = 0.75
FULL_LINE_DOMINANCE_RATIO = 0.60
ALL_SHORT_MAX_LENGTH = 20
SINGLE_PARAGRAPH_MARGIN = 10


def needs_hard_line_break_fix(lines: list[str]) -> bool:
    """Return True when the page looks like hard-wrapped prose.

    The heuristic treats the longest visible line on the page as the reference
    width. Lines near that width are considered "full" body lines, while much
    shorter lines are considered paragraph tails. A page is flagged when full
    lines dominate the page and they appear in blocks that end with a single
    short line, which is the classic shape of wrapped prose.

    There is also a single-paragraph shortcut: if every line belongs to one
    paragraph and only the last line is distinctly shorter than the rest, the
    page is considered hard-wrapped even without blank-line separators.
    """
    stripped_lines = [line.strip() for line in lines if line.strip()]
    if len(stripped_lines) < 2:
        return False

    line_lengths = [len(line) for line in stripped_lines]
    maximum_line_length = max(line_lengths)
    if maximum_line_length < ALL_SHORT_MAX_LENGTH:
        return False

    # If every visible line is already near the maximum width, this page still
    # looks like a solid wrapped text block even without an obviously short tail.
    if min(line_lengths) >= maximum_line_length * FULL_LINE_RATIO:
        return True

    if _is_single_paragraph(lines) and _single_paragraph_needs_fix(line_lengths):
        return True

    full_line_threshold = maximum_line_length * FULL_LINE_RATIO
    short_line_threshold = maximum_line_length * SHORT_LINE_RATIO

    full_line_count = sum(1 for length in line_lengths if length >= full_line_threshold)
    full_line_ratio = full_line_count / len(line_lengths)
    if full_line_ratio < FULL_LINE_DOMINANCE_RATIO:
        return False

    return _has_full_block_then_short_tail(line_lengths, full_line_threshold, short_line_threshold)


def _is_single_paragraph(lines: list[str]) -> bool:
    """Return True when the input has no blank-line paragraph separators."""
    return all(line.strip() for line in lines)


def _single_paragraph_needs_fix(line_lengths: list[int]) -> bool:
    """Detect the simple case of one wrapped paragraph plus a short final tail.

    All body lines must stay within a small fixed margin of the average body
    width, and the last line must be substantially shorter than that body.
    """
    if len(line_lengths) < 3:
        return False

    body_lengths = line_lengths[:-1]
    average_body_length = sum(body_lengths) / len(body_lengths)
    if any(abs(length - average_body_length) > SINGLE_PARAGRAPH_MARGIN for length in body_lengths):
        return False

    last_length = line_lengths[-1]
    return last_length < average_body_length * SHORT_LINE_RATIO


def _has_full_block_then_short_tail(
    line_lengths: list[int],
    full_line_threshold: float,
    short_line_threshold: float,
) -> bool:
    """Look for one or more full-width lines followed by exactly one short line.

    A repeated sequence like `[Full, Full, Short, Full, Full, Short]` is the
    signature this helper is searching for.
    """
    index = 0
    block_signal_count = 0

    while index < len(line_lengths):
        full_run_count = 0
        while index < len(line_lengths) and line_lengths[index] >= full_line_threshold:
            full_run_count += 1
            index += 1

        if full_run_count == 0:
            index += 1
            continue

        short_run_count = 0
        while index < len(line_lengths) and line_lengths[index] < short_line_threshold:
            short_run_count += 1
            index += 1

        if short_run_count == 1:
            block_signal_count += 1

    return block_signal_count > 0
