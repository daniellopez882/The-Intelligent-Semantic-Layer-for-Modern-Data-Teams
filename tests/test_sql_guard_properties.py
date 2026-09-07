"""
Properties the SQL guard has to hold for every input, not just the examples.

The example tests next door say what happens for statements someone thought
of. These say what must be true for statements nobody thought of, and
Hypothesis spends the budget looking for the counter-example. Four of them
are the invariants the read-only guarantee actually rests on:

* the guard never raises, so a malformed statement cannot become a 500
* a write is refused wherever it appears
* a denied function is refused wherever it appears
* an allowed statement stays allowed after normalisation, so what runs on the
  database is what was checked

The generators build SQL from fragments rather than from random characters:
random text is almost never valid SQL, so it would only ever exercise the
parse-error path.
"""

from __future__ import annotations

import sqlglot
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from sql_guard import DENIED_FUNCTIONS, check, with_row_limit

# sqlglot builds its dialect tables on first use, which makes the first example
# in a run much slower than the rest; the deadline would flag that as flaky.
SETTINGS = settings(deadline=None, max_examples=200, suppress_health_check=[HealthCheck.too_slow])

IDENTIFIERS = st.sampled_from(["customers", "orders", "products", "t", "public.orders", '"Odd Name"'])
COLUMNS = st.sampled_from(["*", "id", "name", "total", "created_at", "updated_at", "count(*)"])
WRITE_TEMPLATES = st.sampled_from(
    [
        "DELETE FROM {t}",
        "DELETE FROM {t} WHERE id = 1",
        "UPDATE {t} SET name = 'x'",
        "INSERT INTO {t} VALUES (1)",
        "INSERT INTO {t} SELECT * FROM {t}",
        "DROP TABLE {t}",
        "DROP TABLE IF EXISTS {t}",
        "ALTER TABLE {t} ADD COLUMN c int",
        "CREATE TABLE {t} (id int)",
        "CREATE TABLE {t} AS SELECT 1",
        "TRUNCATE TABLE {t}",
    ]
)
PADDING = st.sampled_from(["", " ", "\n", "\t", "  \n  ", " ;", ";", " ; "])
DIALECTS = st.sampled_from([None, "postgres", "sqlite", "mysql"])


def _outermost_limit(sql: str, dialect: str | None) -> int | None:
    root = sqlglot.parse_one(sql, read=dialect)
    limit = root.args.get("limit")
    if limit is None:
        return None
    return int(limit.expression.this)


@SETTINGS
@given(text=st.text(max_size=200))
def test_check_never_raises(text):
    """A parse failure has to come back as a refusal, never as an exception."""
    verdict = check(text)
    assert isinstance(verdict.allowed, bool)
    assert isinstance(verdict.reason, str) and verdict.reason


@SETTINGS
@given(text=st.text(alphabet=st.characters(codec="utf-8"), max_size=120), dialect=DIALECTS)
def test_check_never_raises_in_any_dialect(text, dialect):
    check(text, dialect=dialect)


@SETTINGS
@given(template=WRITE_TEMPLATES, table=IDENTIFIERS, lead=PADDING, trail=PADDING, dialect=DIALECTS)
def test_a_write_is_always_refused(template, table, lead, trail, dialect):
    sql = lead + template.format(t=table) + trail
    verdict = check(sql, dialect=dialect)
    assert not verdict.allowed, sql
    assert verdict.statement is None


@SETTINGS
@given(
    template=WRITE_TEMPLATES,
    table=IDENTIFIERS,
    column=COLUMNS,
    read_table=IDENTIFIERS,
    dialect=DIALECTS,
)
def test_a_write_appended_to_a_read_is_refused(template, table, column, read_table, dialect):
    """Stacked statements: the read at the front must not carry the write through."""
    sql = f"SELECT {column} FROM {read_table}; {template.format(t=table)}"
    assert not check(sql, dialect=dialect).allowed, sql


@SETTINGS
@given(
    function=st.sampled_from(sorted(DENIED_FUNCTIONS)),
    shape=st.sampled_from(
        [
            "SELECT {f}('x')",
            "SELECT * FROM t WHERE id IN (SELECT {f}('x'))",
            "WITH c AS (SELECT {f}('x') AS v) SELECT * FROM c",
            "SELECT CASE WHEN TRUE THEN {f}('x') ELSE NULL END",
            "SELECT (SELECT {f}('x'))",
            "SELECT 1 UNION SELECT {f}('x')",
            "SELECT COALESCE({f}('x'), 'y')",
            "SELECT * FROM t ORDER BY {f}('x')",
        ]
    ),
    upper=st.booleans(),
)
def test_a_denied_function_is_refused_wherever_it_appears(function, shape, upper):
    name = function.upper() if upper else function
    sql = shape.format(f=name)
    verdict = check(sql, dialect="postgres")
    assert not verdict.allowed, sql
    assert function in verdict.reason.lower(), verdict.reason


@SETTINGS
@given(column=COLUMNS, table=IDENTIFIERS, dialect=DIALECTS)
def test_an_allowed_statement_is_a_fixed_point(column, table, dialect):
    """
    What runs on the database is `verdict.statement`, not the input. If
    normalising changed the verdict, the checked statement and the executed
    statement would be different things.
    """
    verdict = check(f"SELECT {column} FROM {table}", dialect=dialect)
    assert verdict.allowed
    again = check(verdict.statement, dialect=dialect)
    assert again.allowed
    assert again.statement == verdict.statement


@SETTINGS
@given(
    column=COLUMNS,
    table=IDENTIFIERS,
    existing=st.one_of(st.none(), st.integers(min_value=1, max_value=10_000)),
    cap=st.integers(min_value=1, max_value=1_000),
    dialect=DIALECTS,
)
def test_the_row_cap_is_never_exceeded(column, table, existing, cap, dialect):
    sql = f"SELECT {column} FROM {table}"
    if existing is not None:
        sql += f" LIMIT {existing}"
    limited = with_row_limit(sql, cap, dialect=dialect)
    applied = _outermost_limit(limited, dialect)
    assert applied is not None, limited
    assert applied <= cap, limited
    if existing is not None and existing <= cap:
        assert applied == existing, limited


@SETTINGS
@given(
    column=COLUMNS,
    table=IDENTIFIERS,
    inner=st.integers(min_value=10_000, max_value=100_000),
    cap=st.integers(min_value=1, max_value=100),
)
def test_a_limit_in_a_subquery_does_not_satisfy_the_cap(column, table, inner, cap):
    """
    The check this replaced was `if 'LIMIT' not in sql`. A LIMIT inside a
    subquery satisfied it and left the outer query unbounded.
    """
    sql = f"SELECT {column} FROM (SELECT * FROM {table} LIMIT {inner}) AS s"
    applied = _outermost_limit(with_row_limit(sql, cap), None)
    assert applied == cap


@SETTINGS
@given(column=COLUMNS, table=IDENTIFIERS, lead=PADDING, trail=PADDING)
def test_whitespace_and_semicolons_do_not_change_the_verdict(column, table, lead, trail):
    plain = check(f"SELECT {column} FROM {table}")
    padded = check(f"{lead}SELECT {column} FROM {table}{trail}")
    assert plain.allowed == padded.allowed
    assert plain.statement == padded.statement
