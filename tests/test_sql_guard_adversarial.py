"""
An adversarial corpus for the SQL guard.

Every statement here was run against the guard, and the ones marked as findings
were **allowed** before `DENIED_FUNCTIONS` existed. They are not hypothetical:
`SELECT pg_read_file('/etc/passwd')` returned `Verdict(allowed=True,
reason='read-only')`, and a read-only connection would have executed it
happily, because reading a file is not a write.

The corpus is organised by what the attacker gets, so a new payload lands in
the category it belongs to rather than at the end of a list.
"""

from __future__ import annotations

import pytest

from sql_guard import check

# --- statements that change data or schema -----------------------------------

WRITES = [
    ("DELETE FROM customers", None),
    ("UPDATE customers SET name = 'x' WHERE id = 1", None),
    ("INSERT INTO customers VALUES (3, 'c')", None),
    ("DROP TABLE customers", None),
    ("TRUNCATE TABLE orders", "postgres"),
    ("ALTER TABLE customers ADD COLUMN pwned int", None),
    ("CREATE TABLE evil AS SELECT * FROM customers", None),
    ("CREATE TEMP TABLE evil AS SELECT * FROM customers", "postgres"),
    ("CREATE VIEW leak AS SELECT * FROM customers", None),
    ("MERGE INTO customers USING orders ON TRUE WHEN MATCHED THEN DELETE", "postgres"),
    ("GRANT ALL ON customers TO PUBLIC", "postgres"),
    ("REINDEX TABLE customers", "postgres"),
    ("REFRESH MATERIALIZED VIEW mv", "postgres"),
    ("COMMENT ON TABLE customers IS 'x'", "postgres"),
]

# --- more than one statement in one string -----------------------------------

STACKED = [
    ("SELECT 1; DELETE FROM customers", None),
    ("SELECT 1;DELETE FROM customers", None),
    ("SELECT 1; -- harmless\nDELETE FROM customers", None),
    ("SELECT 1;\n/* comment */ DROP TABLE customers", None),
    ("SELECT 1 ; ; DELETE FROM customers", None),
]

# --- a write buried inside something that reads ------------------------------

HIDDEN_WRITES = [
    ("WITH x AS (DELETE FROM customers RETURNING *) SELECT * FROM x", "postgres"),
    ("WITH x AS (UPDATE customers SET name='p' RETURNING id) SELECT * FROM x", "postgres"),
    ("WITH x AS (INSERT INTO customers VALUES (9,'p') RETURNING id) SELECT * FROM x", "postgres"),
]

# --- pure reads that are still attacks: the finding this file exists for ------
# Each of these was allowed before the denylist. None of them writes, so a
# read-only transaction executes every one.

FILE_ACCESS = [
    ("SELECT pg_read_file('/etc/passwd')", "postgres"),
    ("SELECT pg_read_binary_file('/etc/shadow')", "postgres"),
    ("SELECT pg_ls_dir('/var/lib/postgresql/data')", "postgres"),
    ("SELECT pg_stat_file('/etc/passwd')", "postgres"),
    ("SELECT lo_import('/etc/passwd')", "postgres"),
    ("SELECT lo_export(16384, '/tmp/out')", "postgres"),
    ("SELECT readfile('/etc/passwd')", None),
    ("SELECT writefile('/tmp/x', 'y')", None),
    ("SELECT load_file('/etc/passwd')", "mysql"),
]

NETWORK_ACCESS = [
    ("SELECT * FROM dblink('host=10.0.0.1 user=postgres', 'SELECT 1') AS t(x int)", "postgres"),
    ("SELECT dblink_connect('host=169.254.169.254')", "postgres"),
    ("SELECT dblink_exec('conn', 'SELECT 1')", "postgres"),
]

CODE_LOADING = [
    ("SELECT load_extension('/tmp/evil.so')", None),
    ("SELECT fts3_tokenizer('unicode61')", None),
    ("SELECT sys_eval('id')", "mysql"),
    ("SELECT sys_exec('id')", "mysql"),
]

RESOURCE_ABUSE = [
    ("SELECT pg_sleep(600)", "postgres"),
    ("SELECT pg_sleep_for('10 minutes')", "postgres"),
    ("SELECT pg_terminate_backend(1)", "postgres"),
    ("SELECT pg_cancel_backend(1)", "postgres"),
    ("SELECT pg_reload_conf()", "postgres"),
    ("SELECT set_config('default_transaction_read_only', 'off', false)", "postgres"),
    ("SELECT sleep(600)", "mysql"),
    ("SELECT benchmark(100000000, md5('x'))", "mysql"),
]

# --- the same payloads, moved somewhere a shallow check would not look --------

NESTED = [
    ("SELECT * FROM orders WHERE id IN (SELECT pg_sleep(30))", "postgres"),
    ("WITH c AS (SELECT pg_read_file('/etc/passwd') AS f) SELECT * FROM c", "postgres"),
    ("SELECT CASE WHEN 1=1 THEN pg_sleep(30) ELSE 0 END", "postgres"),
    ("SELECT (SELECT pg_read_file('/etc/passwd')) AS leak", "postgres"),
    ("SELECT 1 UNION SELECT pg_sleep(30)", "postgres"),
    ("SELECT a FROM t WHERE b = (SELECT lo_import('/etc/passwd'))", "postgres"),
    ("SELECT * FROM (SELECT pg_ls_dir('/')) AS s", "postgres"),
    ("SELECT COALESCE(pg_read_file('/etc/passwd'), 'x')", "postgres"),
]

CASING = [
    ("SELECT PG_READ_FILE('/etc/passwd')", "postgres"),
    ("SELECT Pg_Sleep(30)", "postgres"),
    ("SeLeCt LOAD_EXTENSION('/tmp/evil.so')", None),
]

# --- statements the parser cannot classify -----------------------------------

UNPARSEABLE_OR_COMMANDS = [
    ("PRAGMA writable_schema = 1", None),
    ("ATTACH DATABASE '/tmp/x.db' AS other", None),
    ("VACUUM", None),
    ("COPY customers TO PROGRAM 'sh -c \"id > /tmp/pwned\"'", "postgres"),
    ("COPY customers FROM '/etc/passwd'", "postgres"),
    ("SET default_transaction_read_only = off", "postgres"),
    ("BEGIN; DELETE FROM customers; COMMIT", "postgres"),
    ("EXPLAIN ANALYZE DELETE FROM customers", "postgres"),
    ("", None),
    ("   ", None),
    (";", None),
    ("SELEC * FORM customers", None),
]

ALL_REFUSED = (
    WRITES
    + STACKED
    + HIDDEN_WRITES
    + FILE_ACCESS
    + NETWORK_ACCESS
    + CODE_LOADING
    + RESOURCE_ABUSE
    + NESTED
    + CASING
    + UNPARSEABLE_OR_COMMANDS
)


@pytest.mark.parametrize(("sql", "dialect"), ALL_REFUSED, ids=[s[:60] for s, _ in ALL_REFUSED])
def test_every_payload_is_refused(sql, dialect):
    verdict = check(sql, dialect=dialect)
    assert not verdict.allowed, f"the guard allowed: {sql}"
    assert verdict.statement is None
    assert verdict.reason


@pytest.mark.parametrize(
    ("sql", "dialect"),
    FILE_ACCESS + NETWORK_ACCESS + CODE_LOADING + RESOURCE_ABUSE,
    ids=[s[:60] for s, _ in FILE_ACCESS + NETWORK_ACCESS + CODE_LOADING + RESOURCE_ABUSE],
)
def test_the_reason_names_the_function(sql, dialect):
    """A refusal has to say which call was the problem, or it cannot be acted on."""
    verdict = check(sql, dialect=dialect)
    assert "is not permitted" in verdict.reason
    assert "()" in verdict.reason


# --- and the queries an analyst actually writes must still run ----------------

LEGITIMATE = [
    ("SELECT * FROM customers", None),
    ("SELECT count(*) FROM orders", None),
    (
        "SELECT c.name, sum(o.total) FROM customers c JOIN orders o ON o.customer_id = c.id GROUP BY c.name",
        None,
    ),
    # The old substring guard refused both of these for containing UPDATE/CREATE.
    ("SELECT * FROM customers WHERE updated_at > '2026-01-01'", None),
    ("SELECT created_at, updated_at FROM orders ORDER BY created_at DESC", None),
    (
        "WITH recent AS (SELECT * FROM orders WHERE created_at > '2026-01-01') SELECT count(*) FROM recent",
        None,
    ),
    ("SELECT * FROM orders WHERE status IN ('paid', 'shipped') LIMIT 10", None),
    ("SELECT lower(name), upper(city), length(email) FROM customers", None),
    ("SELECT * FROM t1 UNION SELECT * FROM t2", None),
    ("SELECT date_trunc('month', created_at), count(*) FROM orders GROUP BY 1", "postgres"),
    # `sleep` is denied; a column called sleep_minutes is not a call.
    ("SELECT sleep_minutes FROM sessions", None),
    ("SELECT id AS load_file FROM t", None),
]


@pytest.mark.parametrize(("sql", "dialect"), LEGITIMATE, ids=[s[:60] for s, _ in LEGITIMATE])
def test_legitimate_queries_still_run(sql, dialect):
    verdict = check(sql, dialect=dialect)
    assert verdict.allowed, f"the guard refused a legitimate query: {sql} ({verdict.reason})"
    assert verdict.statement
