"""
Decide whether a SQL statement may run.

What existed before, in ``tools.py``::

    if not query_upper.startswith('SELECT') and not query_upper.startswith('WITH'):
        return False
    dangerous = ['DELETE', 'DROP', 'TRUNCATE', 'UPDATE', 'INSERT', ...]
    return not any(keyword in query_upper for keyword in dangerous)

Substring matching on the uppercased text. It refused every query that
touched a column called ``updated_at`` or ``created_at`` (they contain UPDATE
and CREATE), and it was not wired to anything: the agent used LangChain's
stock toolkit, whose query tool runs whatever it is given. The only thing
standing between the model and ``DELETE FROM orders`` was a sentence in the
system prompt.

This module parses the statement with sqlglot and walks the tree. It is one
of two controls; the other is that the connection itself is read-only
(``db.py``). A guard that can be argued past is a speed bump, not a lock,
which is why the connection is the real control and this is the one that
produces a useful message.
"""

from __future__ import annotations

from dataclasses import dataclass

import sqlglot
from sqlglot import exp

# Node types that read. Anything else at the top level is refused.
READ_ROOTS = (exp.Select, exp.Union, exp.Intersect, exp.Except)

# Node types that write or change the database, wherever they appear.
WRITE_NODES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.Merge,
    exp.Command,  # PRAGMA, ATTACH, VACUUM, GRANT, ... and anything sqlglot cannot classify
    exp.TruncateTable,
)


@dataclass(frozen=True)
class Verdict:
    allowed: bool
    reason: str
    statement: str | None = None  # the single normalised statement, when allowed


def check(sql: str, dialect: str | None = None) -> Verdict:
    """
    Allow exactly one read-only statement.

    ``dialect`` is passed to sqlglot; ``None`` uses its generic parser, which
    is enough for the SQL an agent writes against SQLite or Postgres.
    """
    text = (sql or "").strip().rstrip(";").strip()
    if not text:
        return Verdict(False, "empty statement")

    try:
        statements = sqlglot.parse(text, read=dialect)
    except sqlglot.errors.ParseError as error:
        return Verdict(False, f"could not parse: {str(error).splitlines()[0][:200]}")

    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        return Verdict(False, f"expected one statement, got {len(statements)}")

    root = statements[0]
    # A CTE is a Select/Union with a `with` argument; sqlglot roots it at the
    # query node, so this also admits WITH ... SELECT.
    if not isinstance(root, READ_ROOTS):
        return Verdict(False, f"only SELECT statements may run (got {type(root).__name__})")

    for node in root.walk():
        if isinstance(node, WRITE_NODES):
            return Verdict(False, f"{type(node).__name__} is not permitted inside a query")

    return Verdict(True, "read-only", root.sql(dialect=dialect))


def with_row_limit(statement: str, max_rows: int, dialect: str | None = None) -> str:
    """
    Cap the number of rows a statement can return.

    The previous ``_add_limit`` appended `` LIMIT 100`` if the word LIMIT did
    not appear anywhere in the text. A LIMIT inside a subquery, or a column
    named ``limit_price``, satisfied that check and left the outer query
    unbounded. This sets the limit on the outermost query node, lowering an
    existing one if it is larger.
    """
    root = sqlglot.parse_one(statement, read=dialect)
    existing = root.args.get("limit")
    if existing is not None:
        try:
            current = int(existing.expression.this)
        except (AttributeError, TypeError, ValueError):
            current = None
        if current is not None and current <= max_rows:
            return root.sql(dialect=dialect)
    return root.limit(max_rows).sql(dialect=dialect)
