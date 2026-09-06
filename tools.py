"""
The three things the agent can do: list tables, describe one, run a read-only query.

The previous ``tools.py`` defined a ``SafeSQLExecutor`` with a substring-based
safety check and a ``_add_limit`` that could be fooled by a LIMIT in a
subquery -- and none of it was used. The agent ran LangChain's stock SQL
toolkit, whose query tool executes whatever it is given, on a read-write
connection.

Every query here passes ``sql_guard.check`` and runs on an engine opened
read-only (``db.py``). Results are returned as data, not just text, so the
page can show and chart them without executing the statement a second time.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import sqlalchemy
from sqlalchemy.engine import Engine

import sql_guard

logger = logging.getLogger("sql_agent.tools")

MAX_CELL_CHARS = 200
MAX_SAMPLE_ROWS = 3


@dataclass
class QueryResult:
    sql: str
    columns: list[str]
    rows: list[dict[str, Any]]
    truncated: bool = False
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    def as_text(self, max_rows: int = 20) -> str:
        """A compact rendering for the model's context."""
        if self.error:
            return f"ERROR: {self.error}"
        if not self.rows:
            return "The query ran and returned no rows."
        shown = self.rows[:max_rows]
        head = " | ".join(self.columns)
        body = "\n".join(" | ".join(_cell(row.get(col)) for col in self.columns) for row in shown)
        note = ""
        if len(self.rows) > max_rows:
            note = f"\n... {len(self.rows) - max_rows} more row(s) not shown"
        if self.truncated:
            note += "\n(result capped at the configured row limit)"
        return f"{len(self.rows)} row(s)\n{head}\n{body}{note}"


def _cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text if len(text) <= MAX_CELL_CHARS else text[: MAX_CELL_CHARS - 1] + "…"


@dataclass
class SQLTools:
    """Bound to one read-only engine."""

    engine: Engine
    max_rows: int = 100
    dialect: str | None = None
    last_result: QueryResult | None = field(default=None, init=False)

    # -- schema ---------------------------------------------------------------

    def list_tables(self) -> str:
        """List the tables in the database."""
        names = sqlalchemy.inspect(self.engine).get_table_names()
        return ", ".join(names) if names else "(no tables)"

    def describe_table(self, table: str) -> str:
        """Columns, types and a few sample rows for one table."""
        inspector = sqlalchemy.inspect(self.engine)
        if table not in inspector.get_table_names():
            return f"No table named {table!r}. Tables: {self.list_tables()}"
        cols = inspector.get_columns(table)
        lines = [f"{c['name']} {c['type']}" for c in cols]
        quoted = self.engine.dialect.identifier_preparer.quote(table)
        # nosec B608 - `quoted` is a table name taken from the inspector and quoted by
        # the dialect two lines above, and MAX_SAMPLE_ROWS is a module constant.
        sample = self.run_query(f"SELECT * FROM {quoted} LIMIT {MAX_SAMPLE_ROWS}")  # nosec B608
        self.last_result = None  # a sample is not an answer
        return f"Table {table}:\n" + "\n".join(lines) + "\n\nSample rows:\n" + sample.as_text()

    # -- query ----------------------------------------------------------------

    def run_query(self, sql: str) -> QueryResult:
        """Run one read-only SELECT. Refuses everything else before it reaches the database."""
        verdict = sql_guard.check(sql, dialect=self.dialect)
        if not verdict.allowed:
            result = QueryResult(sql=sql, columns=[], rows=[], error=f"refused: {verdict.reason}")
            self.last_result = result
            return result

        statement = sql_guard.with_row_limit(verdict.statement, self.max_rows + 1, self.dialect)
        try:
            with self.engine.connect() as conn:
                cursor = conn.execute(sqlalchemy.text(statement))
                columns = list(cursor.keys())
                fetched = cursor.fetchall()
        except sqlalchemy.exc.SQLAlchemyError as error:
            logger.warning("query failed: %s", type(error).__name__)
            result = QueryResult(sql=statement, columns=[], rows=[], error=_db_error(error))
            self.last_result = result
            return result

        truncated = len(fetched) > self.max_rows
        rows = [dict(zip(columns, row, strict=True)) for row in fetched[: self.max_rows]]
        result = QueryResult(sql=statement, columns=columns, rows=rows, truncated=truncated)
        self.last_result = result
        return result


def _db_error(error: Exception) -> str:
    """The driver's message without the SQL echo sqlalchemy appends."""
    text = str(getattr(error, "orig", error))
    return text.split("\n[SQL:")[0][:300]
