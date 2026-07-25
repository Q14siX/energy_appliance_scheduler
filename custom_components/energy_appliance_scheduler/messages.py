"""Alexa message-template helpers."""

from __future__ import annotations

from string import Formatter
from typing import Any

from .const import ALEXA_TEMPLATE_FIELDS


def validate_message_template(value: str) -> bool:
    """Return whether a message template only uses supported placeholders."""
    try:
        for _, field_name, format_spec, conversion in Formatter().parse(value):
            if field_name is None:
                continue
            if field_name not in ALEXA_TEMPLATE_FIELDS:
                return False
            if format_spec or conversion:
                return False
    except ValueError:
        return False
    return True


def render_message_template(template: str, values: dict[str, Any]) -> str:
    """Render a validated template and normalize whitespace."""
    safe_values = {field: str(values.get(field, "") or "") for field in ALEXA_TEMPLATE_FIELDS}
    try:
        rendered = template.format_map(safe_values)
    except (KeyError, ValueError):
        rendered = template
    return " ".join(rendered.split()).strip()
