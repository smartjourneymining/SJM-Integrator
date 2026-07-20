"""
Pure helpers for AGE's agtype, with no third-party dependencies so they can be
used (and unit-tested) without psycopg2 installed.
"""
import json
import re

# Trailing "::vertex" / "::edge" / "::path" type annotation on agtype values.
_AGTYPE_SUFFIX = re.compile(r"::(vertex|edge|path)\s*$")


def parse_agtype(value):
    """Convert a raw agtype string returned by the driver into a Python object."""
    if value is None or not isinstance(value, str):
        return value
    s = _AGTYPE_SUFFIX.sub("", value.strip()).strip()
    try:
        return json.loads(s)
    except (json.JSONDecodeError, ValueError):
        return value


def quote_literal(value):
    """Render a Python value as a Cypher literal for inline query building.

    Numbers and booleans pass through; everything else becomes a single-quoted,
    escaped string.
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    s = str(value).replace("\\", "\\\\").replace("'", "\\'")
    return f"'{s}'"
