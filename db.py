"""
Database connections that cannot write.

The agent's connection was ``SQLDatabase.from_uri(database_uri)`` -- a normal
read-write connection -- and the UI re-ran the model's last statement through
a second read-write engine of its own, with no check at all. "Only SELECT is
allowed" was a line in the prompt.

A read-only connection is a property of the database session, not of the
text sent over it. For SQLite that is ``mode=ro``; for Postgres it is
``default_transaction_read_only=on``, which makes every write fail server-side
regardless of what the application sends. ``sql_guard`` still runs first, so
the user reads "only SELECT statements may run" instead of a driver error.
"""

from __future__ import annotations

import logging
from urllib.parse import urlsplit, urlunsplit

import sqlalchemy
from sqlalchemy.engine import Engine, make_url

logger = logging.getLogger("sql_agent.db")


def read_only_url(database_url: str) -> str:
    """
    The same database, opened read-only.

    SQLite: ``sqlite:///path.db`` -> ``sqlite:///file:path.db?mode=ro&uri=true``.
    Postgres: adds ``options=-c default_transaction_read_only=on``.
    Anything else is refused rather than silently left writable.
    """
    url = make_url(database_url)
    backend = url.get_backend_name()

    if backend == "sqlite":
        database = url.database or ""
        if database in ("", ":memory:"):
            # An in-memory database has nothing to protect and no file to open ro.
            return database_url
        path = database[len("file:") :].split("?", 1)[0] if database.startswith("file:") else database
        return f"sqlite:///file:{path}?mode=ro&uri=true"

    if backend in ("postgresql", "postgres"):
        query = dict(url.query)
        existing = query.get("options", "")
        flag = "-c default_transaction_read_only=on"
        if flag not in existing:
            query["options"] = (existing + " " + flag).strip()
        return url.set(query=query).render_as_string(hide_password=False)

    raise ValueError(
        f"no read-only mode is implemented for the {backend!r} backend; "
        "refusing to open a writable connection for the agent"
    )


def read_only_engine(database_url: str) -> Engine:
    """An engine that cannot write, with pooling and pre-ping."""
    return sqlalchemy.create_engine(read_only_url(database_url), pool_pre_ping=True)


def redacted(database_url: str) -> str:
    """The URL with any password removed, for logs and the UI."""
    try:
        return make_url(database_url).render_as_string(hide_password=True)
    except Exception:  # not a URL sqlalchemy understands; show nothing sensitive
        parts = urlsplit(database_url)
        netloc = parts.hostname or ""
        return urlunsplit((parts.scheme, netloc, parts.path, "", ""))
