"""The sample database and the chart picker."""

from __future__ import annotations

import sqlite3
from datetime import datetime

import pandas as pd

from setup_db import CUSTOMER_COUNT, ORDER_COUNT, PRODUCTS, create_sample_database
from visualizer import auto_visualize, should_visualize, summary_stats


class TestSampleDatabase:
    def test_the_counts_match_what_is_documented(self, tmp_path):
        path = create_sample_database(str(tmp_path / "a.db"))
        conn = sqlite3.connect(path)
        assert conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0] == CUSTOMER_COUNT
        assert conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == len(PRODUCTS)
        assert conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == ORDER_COUNT

    def test_the_same_seed_gives_the_same_data(self, tmp_path):
        """random was unseeded; every run produced a different demo."""
        fixed = datetime(2026, 9, 1)
        a = create_sample_database(str(tmp_path / "a.db"), seed=7, now=fixed)
        b = create_sample_database(str(tmp_path / "b.db"), seed=7, now=fixed)
        rows_a = sqlite3.connect(a).execute("SELECT * FROM orders ORDER BY order_id").fetchall()
        rows_b = sqlite3.connect(b).execute("SELECT * FROM orders ORDER BY order_id").fetchall()
        assert rows_a == rows_b

    def test_totals_are_consistent(self, tmp_path):
        path = create_sample_database(str(tmp_path / "a.db"))
        bad = (
            sqlite3.connect(path)
            .execute("SELECT COUNT(*) FROM orders WHERE ABS(total_amount - unit_price * quantity) > 0.011")
            .fetchone()[0]
        )
        assert bad == 0

    def test_an_existing_file_is_replaced(self, tmp_path):
        path = tmp_path / "a.db"
        path.write_bytes(b"not a database")
        create_sample_database(str(path))
        assert sqlite3.connect(path).execute("SELECT COUNT(*) FROM products").fetchone()[0] == 12

    def test_no_print_statements(self):
        """print() of emoji raised UnicodeEncodeError on a cp1252 console."""
        import ast
        import inspect

        import setup_db

        tree = ast.parse(inspect.getsource(setup_db))
        calls = [
            n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "print"
        ]
        assert calls == []


class TestVisualizer:
    def test_the_callers_frame_is_not_renamed(self):
        """auto_visualize mutated df.columns in place."""
        df = pd.DataFrame({"order_date": ["2026-01-01", "2026-02-01"], "total_amount": [1.0, 2.0]})
        auto_visualize(df)
        assert list(df.columns) == ["order_date", "total_amount"]

    def test_a_frame_with_no_numbers_is_not_charted(self):
        assert auto_visualize(pd.DataFrame({"a": ["x", "y"]})) is None

    def test_one_row_is_not_charted(self):
        assert should_visualize(pd.DataFrame({"a": [1]})) is False

    def test_a_date_and_a_number_make_a_line(self):
        df = pd.DataFrame({"order_date": ["2026-01-01", "2026-02-01"], "total_amount": [1.0, 2.0]})
        fig = auto_visualize(df)
        assert fig is not None and fig.data[0].type == "scatter"

    def test_a_category_and_a_number_make_a_bar_or_pie(self):
        df = pd.DataFrame({"country": list("ABCDEFG"), "revenue": range(7)})
        assert auto_visualize(df).data[0].type == "bar"
        assert auto_visualize(df.head(3)).data[0].type == "pie"

    def test_summary_names_money_columns(self):
        text = summary_stats(pd.DataFrame({"total_amount": [1.5, 2.5], "quantity": [1, 3]}))
        assert "Total Amount: total 4.00, mean 2.00" in text
        assert "Quantity: sum 4, mean 2.0" in text
