# ADR 0001 — Read-only is a property of the connection, and the guard is a parser

**Status:** accepted

## Context

The agent's system prompt said "Never generate any queries that modify data."
That was the control. The connection was `SQLDatabase.from_uri(url)` —
read-write — and the agent ran LangChain's stock SQL toolkit, whose query tool
executes whatever it receives. Reproduced: `db.run("DELETE FROM customers")`
on that connection left zero rows.

A `SafeSQLExecutor` existed in `tools.py` with a substring check
(`'CREATE' in query_upper`) that refused `SELECT created_at FROM t`, and a
limit routine fooled by a LIMIT in a subquery. It was imported and never used.

A question-level filter (`"delete" in question.lower()`) refused "which
products were updated last month?" and admitted "remove every row from the
orders table".

## Decision

Two layers, in this order:

1. **The connection cannot write.** SQLite is opened with `mode=ro`; Postgres
   sessions get `default_transaction_read_only=on`. A backend without a
   read-only mode is refused rather than opened writable. CI runs a `DELETE`
   through the agent's own engine and requires the database to refuse it.
2. **The statement is parsed.** `sql_guard.check` parses with sqlglot,
   requires exactly one statement rooted at a SELECT/UNION/INTERSECT/EXCEPT,
   and walks the tree for any write or command node. The row limit is set on
   the outermost query node, not appended when the word LIMIT is absent.

The parser gives the user a sentence; the connection gives the guarantee.
Neither the question nor the prompt is trusted for safety.

## Consequences

`PRAGMA`, `ATTACH`, `VACUUM` and data-modifying CTEs are refused. A column
named `created_at` is not. The page never re-executes the model's SQL through
a second engine; it charts the rows the agent already fetched.
