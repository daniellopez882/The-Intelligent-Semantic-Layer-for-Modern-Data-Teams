"""
Read-only connections.

Reproduced on the original: ``SQLDatabase.from_uri(...)`` -- the agent's
connection -- ran ``DELETE FROM customers`` and left zero rows.
"""

from __future__ import annotations

import sqlite3

import pytest
import sqlalchemy

from db import read_only_engine, read_only_url, redacted


class TestSQLite:
    def test_a_delete_through_the_agents_engine_is_refused_by_the_database(self, tiny_db):
        engine = read_only_engine(tiny_db)
        with pytest.raises(sqlalchemy.exc.SQLAlchemyError), engine.begin() as conn:
            conn.execute(sqlalchemy.text("DELETE FROM customers"))
        path = tiny_db[len("sqlite:///") :]
        assert sqlite3.connect(path).execute("SELECT COUNT(*) FROM customers").fetchone()[0] == 2

    def test_reads_still_work(self, tiny_db):
        with read_only_engine(tiny_db).connect() as conn:
            assert conn.execute(sqlalchemy.text("SELECT COUNT(*) FROM customers")).scalar() == 2

    def test_the_url_carries_mode_ro(self):
        assert read_only_url("sqlite:///data/x.db") == "sqlite:///file:data/x.db?mode=ro&uri=true"

    def test_an_already_read_only_url_is_not_doubled(self):
        once = read_only_url("sqlite:///x.db")
        assert read_only_url(once) == once

    def test_memory_databases_pass_through(self):
        assert read_only_url("sqlite://") == "sqlite://"


class TestPostgres:
    def test_the_session_is_forced_read_only(self):
        url = read_only_url("postgresql://u:p@h:5432/d")
        assert "default_transaction_read_only%3Don" in url or "default_transaction_read_only=on" in url

    def test_existing_options_are_kept(self):
        url = read_only_url("postgresql://u:p@h/d?options=-c%20statement_timeout%3D5000")
        assert "statement_timeout" in url
        assert "default_transaction_read_only" in url


class TestOtherBackends:
    def test_an_unknown_backend_is_refused_rather_than_left_writable(self):
        with pytest.raises(ValueError, match="read-only"):
            read_only_url("mysql://u:p@h/d")


class TestRedaction:
    def test_the_password_is_removed(self):
        assert "hunter2" not in redacted("postgresql://u:hunter2@h/d")
        assert "h/d" in redacted("postgresql://u:hunter2@h/d")

    def test_sqlite_paths_are_shown(self):
        assert "x.db" in redacted("sqlite:///x.db")
