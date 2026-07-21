"""Bounded, secret-free provider repair instructions."""

from __future__ import annotations

from orchestra.repositories.repository import dumps


def repair_messages(errors: list[str], required_schema: dict) -> list[dict[str, str]]:
    """Return a minimal repair prompt containing no prior prompt or credential data."""
    return [
        {
            "role": "system",
            "content": "You repair one Pico Probe node response. Return JSON only. Do not claim tool execution, verification, or artifacts.",
        },
        {
            "role": "user",
            "content": "Produce a replacement response satisfying the schema and validation errors below.\nERRORS:\n"
            + dumps(errors)
            + "\nREQUIRED_SCHEMA:\n"
            + dumps(required_schema),
        },
    ]
