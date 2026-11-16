"""Shared protocol-family matching for the validator and the diagram renderer.

The table lives here once. ``family`` maps a free-text protocol or technology
string to a family name, or None when nothing in the table matches.
"""
from __future__ import annotations

import re

# Table order is match order; multi-token entries are tried first.
PROTOCOL_FAMILY_TABLE: tuple[tuple[str, str], ...] = (
    ("http", "web"),
    ("https", "web"),
    ("rest", "web"),
    ("graphql", "web"),
    ("websocket", "web"),
    ("grpc", "grpc"),
    ("http/2", "grpc"),
    ("sql", "sql"),
    ("postgresql", "sql"),
    ("mysql", "sql"),
    ("mssql", "sql"),
    ("tds", "sql"),
    ("oracle", "sql"),
    ("sqlite", "sql"),
    ("mariadb", "sql"),
    ("redis", "redis"),
    ("amqp", "amqp"),
    ("kafka", "kafka"),
    ("sqs", "sqs"),
    ("sns", "sns"),
    ("dynamodb", "dynamodb"),
    ("s3", "s3"),
    ("snowflake", "snowflake"),
    ("bigquery", "bigquery"),
    ("mongodb", "mongodb"),
    ("other", "other"),
)


def _ordered_entries() -> tuple[tuple[str, str], ...]:
    multi = [e for e in PROTOCOL_FAMILY_TABLE if re.search(r"[^a-z0-9]", e[0])]
    single = [e for e in PROTOCOL_FAMILY_TABLE if not re.search(r"[^a-z0-9]", e[0])]
    return tuple(multi + single)


_ENTRIES = tuple(
    (re.compile(r"(?<![a-z0-9])" + re.escape(entry) + r"(?![a-z0-9])"), fam)
    for entry, fam in _ordered_entries()
)


def family(text: str) -> str | None:
    """Return the protocol family of ``text``, or None when no entry matches."""
    if not isinstance(text, str):
        return None
    lowered = text.lower()
    for pattern, fam in _ENTRIES:
        if pattern.search(lowered):
            return fam
    return None
