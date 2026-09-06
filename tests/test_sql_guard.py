"""
The statement guard.

Reproduced on the original: the substring check refused
``SELECT created_at FROM t`` (CREATE inside created_at) and the limit logic
left a query unbounded whenever a LIMIT appeared anywhere in the text.
"""

from __future__ import annotations

import pytest

from sql_guard import check, with_row_limit


class TestReadsAreAllowed:
    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT 1",
            "SELECT created_at, updated_at FROM customers",
            "select name from customers where segment = 'DELETE'",
            "WITH recent AS (SELECT * FROM orders WHERE order_date > '2026-01-01') "
            "SELECT COUNT(*) FROM recent",
            "SELECT a FROM t UNION SELECT b FROM u",
            "SELECT * FROM orders WHERE product_id IN (SELECT product_id FROM products LIMIT 5)",
            "SELECT * FROM t;",
        ],
    )
    def test_select_forms(self, sql):
        verdict = check(sql)
        assert verdict.allowed, verdict.reason

    def test_column_names_containing_keywords_are_fine(self):
        """The old check refused these."""
        assert check("SELECT created_at FROM t").allowed
        assert check("SELECT updated_at FROM t").allowed


class TestWritesAreRefused:
    @pytest.mark.parametrize(
        "sql",
        [
            "DELETE FROM customers",
            "UPDATE customers SET name = 'x'",
            "INSERT INTO customers VALUES (3, 'c', '2026-03-01')",
            "DROP TABLE customers",
            "CREATE TABLE evil (x)",
            "ALTER TABLE customers ADD COLUMN y",
            "PRAGMA writable_schema = 1",
            "ATTACH DATABASE '/tmp/x' AS other",
            "VACUUM",
        ],
    )
    def test_non_select_statements(self, sql):
        verdict = check(sql)
        assert not verdict.allowed, sql
        assert verdict.statement is None

    def test_two_statements_are_refused(self):
        verdict = check("SELECT 1; DELETE FROM customers")
        assert not verdict.allowed
        assert "one statement" in verdict.reason

    def test_a_write_hidden_in_a_cte_is_refused(self):
        """Some dialects allow data-modifying CTEs; the walk catches the node."""
        verdict = check("WITH x AS (DELETE FROM customers RETURNING *) SELECT * FROM x", dialect="postgres")
        assert not verdict.allowed

    @pytest.mark.parametrize("sql", ["", "   ", ";"])
    def test_empty_input(self, sql):
        assert not check(sql).allowed

    def test_garbage_does_not_raise(self):
        verdict = check("SELEC * FORM")
        assert not verdict.allowed
        assert "parse" in verdict.reason or "SELECT" in verdict.reason


class TestRowLimit:
    def test_a_limit_is_added(self):
        assert "LIMIT 10" in with_row_limit("SELECT * FROM t", 10)

    def test_a_larger_existing_limit_is_lowered(self):
        out = with_row_limit("SELECT * FROM t LIMIT 5000", 10)
        assert "LIMIT 10" in out
        assert "5000" not in out

    def test_a_smaller_existing_limit_is_kept(self):
        assert "LIMIT 3" in with_row_limit("SELECT * FROM t LIMIT 3", 10)

    def test_a_limit_inside_a_subquery_does_not_satisfy_the_outer_limit(self):
        """The old code checked for the word LIMIT anywhere in the text."""
        out = with_row_limit("SELECT * FROM t WHERE id IN (SELECT id FROM u LIMIT 5)", 10)
        assert out.rstrip().upper().endswith("LIMIT 10")

    def test_a_column_named_limit_price_does_not_count_as_a_limit(self):
        out = with_row_limit("SELECT limit_price FROM t", 10)
        assert out.rstrip().upper().endswith("LIMIT 10")
