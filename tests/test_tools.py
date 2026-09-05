"""The three tools, on a real SQLite file opened read-only."""

from __future__ import annotations

from db import read_only_engine
from tools import SQLTools


def tools_for(url, max_rows=100):
    return SQLTools(read_only_engine(url), max_rows=max_rows)


class TestSchema:
    def test_tables_are_listed(self, sample_db):
        names = tools_for(sample_db).list_tables()
        assert "customers" in names and "orders" in names and "products" in names

    def test_a_table_is_described_with_columns_and_samples(self, sample_db):
        text = tools_for(sample_db).describe_table("products")
        assert "product_name" in text
        assert "Sample rows" in text
        assert "Quantum Laptop Pro" in text

    def test_an_unknown_table_names_the_known_ones(self, sample_db):
        text = tools_for(sample_db).describe_table("nope")
        assert "No table named 'nope'" in text
        assert "customers" in text

    def test_describing_does_not_leave_a_sample_as_the_last_result(self, sample_db):
        tools = tools_for(sample_db)
        tools.describe_table("products")
        assert tools.last_result is None


class TestQuery:
    def test_rows_come_back_as_data(self, sample_db):
        result = tools_for(sample_db).run_query(
            "SELECT product_id, product_name FROM products ORDER BY product_id"
        )
        assert result.ok
        assert result.columns == ["product_id", "product_name"]
        assert result.rows[0] == {"product_id": 1, "product_name": "Quantum Laptop Pro"}

    def test_the_row_cap_is_applied_and_reported(self, sample_db):
        result = tools_for(sample_db, max_rows=10).run_query("SELECT * FROM orders")
        assert len(result.rows) == 10
        assert result.truncated is True

    def test_a_result_under_the_cap_is_not_marked_truncated(self, sample_db):
        result = tools_for(sample_db, max_rows=100).run_query("SELECT * FROM products")
        assert len(result.rows) == 12
        assert result.truncated is False

    def test_a_write_is_refused_before_reaching_the_database(self, tiny_db):
        tools = tools_for(tiny_db)
        result = tools.run_query("DELETE FROM customers")
        assert not result.ok
        assert "refused" in result.error
        assert tools.run_query("SELECT COUNT(*) AS n FROM customers").rows[0]["n"] == 2

    def test_a_database_error_is_returned_not_raised(self, sample_db):
        result = tools_for(sample_db).run_query("SELECT nonexistent_column FROM products")
        assert not result.ok
        assert "nonexistent_column" in result.error

    def test_the_error_does_not_echo_the_whole_statement_twice(self, sample_db):
        result = tools_for(sample_db).run_query("SELECT nope FROM products")
        assert "[SQL:" not in result.error


class TestTextRendering:
    def test_empty_results_say_so(self, sample_db):
        result = tools_for(sample_db).run_query("SELECT * FROM products WHERE product_id = -1")
        assert result.as_text() == "The query ran and returned no rows."

    def test_long_cells_are_shortened_for_the_model(self, tiny_db):
        tools = tools_for(tiny_db)
        result = tools.run_query("SELECT " + "'" + "x" * 500 + "' AS long")
        assert len(result.as_text()) < 400

    def test_more_rows_than_shown_is_noted(self, sample_db):
        result = tools_for(sample_db).run_query("SELECT * FROM orders")
        assert "more row(s) not shown" in result.as_text(max_rows=5)
