"""
Delimiter extraction from the ISA segment.

The ISA segment is fixed-width (106 characters). Delimiters are extracted
from well-known positions:
  - Element separator  → character at position 3
  - Sub-element separator → character at position 104
  - Segment terminator   → character at position 105
"""
from parser.models import Delimiters


_ISA_MIN_LENGTH = 106


class DelimiterExtractionError(Exception):
    """Raised when the ISA segment cannot be parsed for delimiters."""


def extract_delimiters(raw: str) -> Delimiters:
    """
    Extract X12 delimiters from the ISA header.

    Args:
        raw: The full raw EDI file content (or at least the first 106 chars).

    Returns:
        A Delimiters model with element_separator, sub_element_separator,
        and segment_terminator.

    Raises:
        DelimiterExtractionError: If the content is too short or doesn't
            start with 'ISA'.
    """
    # Strip leading whitespace / BOM
    content = raw.lstrip("\ufeff \t\r\n")

    if len(content) < _ISA_MIN_LENGTH:
        raise DelimiterExtractionError(
            f"File too short to contain a valid ISA segment "
            f"(need >= {_ISA_MIN_LENGTH} chars, got {len(content)})"
        )

    if not content[:3].upper().startswith("ISA"):
        raise DelimiterExtractionError(
            f"File does not begin with 'ISA'. Found: '{content[:10]}...'"
        )

    element_sep = content[3]
    sub_element_sep = content[104]
    segment_term = content[105]

    return Delimiters(
        element_separator=element_sep,
        sub_element_separator=sub_element_sep,
        segment_terminator=segment_term,
    )
