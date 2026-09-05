# Threat model

Scope: a Streamlit page and the agent behind it, attached to one database
the operator points it at. No authentication of its own; Streamlit's server
is the surface. No multi-tenancy.

## What it holds

| Asset | Where | Why it matters |
|---|---|---|
| The database | wherever `DATABASE_URL` points | The whole point. Opened read-only |
| `LLM_API_KEY` | `.env` / environment | Billable |
| Questions and answers | session state; `evaluations.csv` if feedback is on | Business questions are business information |

## Threats

### T1 — The model writes to the database *(was open)*

The connection was read-write and the only guard was a prompt sentence.
Reproduced: a `DELETE` through the agent's connection emptied a table.

**Controls.** Read-only connection (`mode=ro` / `default_transaction_read_only=on`);
parsed statement guard admitting one SELECT; row cap on the outermost query;
the page never re-executes SQL. CI runs a `DELETE` through the engine and
requires the database to refuse it.

**Residual.** A read-only session still reads everything the database user
can see. Grant that user the minimum.

### T2 — Prompt injection through data

Table contents are shown to the model (`describe_table` samples, query
results). A row containing instructions can shape the model's next tool
call or its answer.

**Controls.** The worst outcome of a shaped tool call is a refused write or
a different SELECT; the connection bounds the blast radius. Cells are
truncated before they reach the model.

**Residual.** A misleading answer. The page labels every number as coming
from a query the agent ran and shows the SQL and the rows, so a reader can
check.

### T3 — Data exfiltration through the page

Anyone who can reach the Streamlit port can ask the database anything the
read-only user can read.

**Controls.** None in this repository. Put the page behind an authenticating
reverse proxy, and point it at a database user with the minimum grants.

### T4 — Spreadsheet formula injection via feedback

`evaluations.csv` used to receive the user's question verbatim. A question
beginning with `=` becomes a formula when the file is opened in a
spreadsheet. Cells starting with `= + - @` are now prefixed with `'`.

### T5 — Model spend

Every question costs a model call plus tool calls up to `max_steps` (8).
There is no rate limit and no per-user quota.

### T6 — Supply chain

Dependencies were unconstrained, so what an install resolved depended on the
day. Everything is pinned; `pip-audit` and `bandit` run in CI; the container
runs as uid 10001.

## Not addressed

- No authentication or rate limiting on the page.
- No audit log of questions beyond the optional feedback file.
- The sample database is synthetic; nothing here has been run against a
  model or a production database.
