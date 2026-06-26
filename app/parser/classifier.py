class UnsupportedFormatError(Exception):
    """Exception raised when the input format is not supported."""
    pass


def classify_format(content: str) -> str:
    """Read the first few characters of content and classify the file format.
    
    Returns 'edi' or 'json', or raises UnsupportedFormatError.
    """
    prefix = content[:10].lstrip()
    if prefix.startswith("ISA"):
        return "edi"
    elif prefix.startswith("{") or prefix.startswith("["):
        return "json"
    else:
        raise UnsupportedFormatError(
            f"Unsupported file format. Header prefix: '{prefix[:5]}'"
        )
