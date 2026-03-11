"""Utility helpers."""


def parse_roll_numbers(text: str) -> list[str]:
    """
    Parse roll numbers from a text input.
    Supports comma, newline, space, and semicolon separators.
    """
    import re
    rolls = [r.strip() for r in re.split(r"[,;\n\r\s]+", text) if r.strip()]
    return rolls
