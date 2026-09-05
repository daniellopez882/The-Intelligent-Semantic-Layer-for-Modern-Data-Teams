"""
The page, driven headlessly with Streamlit's AppTest.

Reproduced from the original source: the feedback buttons lived inside
``if run_query:``, so the rerun a click causes never rendered them and the
click was lost; the feedback row logged the SQL as "N/A"; and the sidebar
showed three status lines that nothing checked.

AppTest executes app.py as a fresh script, so nothing in the test module can
be patched into it. The real agent runs against the sample database with a
scripted model installed through ``llm.set_model_factory`` -- the same seam
the agent tests use -- and Streamlit's resource cache is cleared so every test
builds its own agent.
"""

from __future__ import annotations

import csv
import pathlib

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from config import settings
from tests.conftest import ScriptedModel

APP = str(pathlib.Path(__file__).resolve().parents[1] / "app.py")

REVENUE_SQL = (
    "SELECT c.country, SUM(o.total_amount) AS revenue FROM orders o "
    "JOIN customers c ON o.customer_id = c.customer_id GROUP BY c.country ORDER BY revenue DESC"
)


@pytest.fixture
def page(sample_db, tmp_path, monkeypatch):
    feedback = tmp_path / "evaluations.csv"
    monkeypatch.setattr(settings, "DATABASE_URL", sample_db)
    monkeypatch.setattr(settings, "FEEDBACK_PATH", str(feedback))
    monkeypatch.setattr(settings, "LLM_API_KEY", "test-key-not-real")
    st.cache_resource.clear()

    def script(*entries):
        model = ScriptedModel(entries)
        from llm import set_model_factory

        set_model_factory(lambda: model)
        return model

    at = AppTest.from_file(APP, default_timeout=60)
    return at, script, feedback


def ask(at, text):
    at.text_area(key="question_input").set_value(text)
    next(b for b in at.button if b.label == "Run").click()
    return at.run()


def sidebar_text(at):
    return (
        " ".join(el.value for el in at.sidebar.success) + " " + " ".join(el.value for el in at.sidebar.error)
    )


class TestStatusIsMeasured:
    def test_the_sidebar_shows_checks_not_slogans(self, page):
        at, _, _ = page
        at.run()
        text = sidebar_text(at)
        assert "read-only" in text
        assert "row limit" in text
        for slogan in ("Online", "Row-Level Active", "Schema Cache"):
            assert slogan not in text

    def test_a_missing_model_key_is_reported_not_claimed_online(self, page, monkeypatch):
        at, _, _ = page
        monkeypatch.setattr(settings, "LLM_API_KEY", "")
        at.run()
        assert "LLM_API_KEY not set" in " ".join(el.value for el in at.sidebar.error)


class TestAskAndFeedback:
    def test_an_answer_and_its_rows_are_rendered(self, page):
        at, script, _ = page
        script([("run_query", {"sql": REVENUE_SQL})], "USA leads on revenue.")
        at.run()
        ask(at, "revenue by country")
        assert any("USA leads on revenue." in el.value for el in at.markdown)
        assert len(at.dataframe) == 1
        assert "revenue" in at.dataframe[0].value.columns

    def test_feedback_survives_the_rerun_and_records_the_sql(self, page):
        """The click reruns the script; the buttons must still exist, and the SQL must be logged."""
        at, script, feedback = page
        script([("run_query", {"sql": REVENUE_SQL})], "USA leads on revenue.")
        at.run()
        ask(at, "revenue by country")
        next(b for b in at.button if b.key == "fb_ok").click()
        at.run()
        rows = list(csv.DictReader(feedback.open(encoding="utf-8")))
        assert len(rows) == 1
        assert rows[0]["verdict"] == "correct"
        assert rows[0]["sql"].upper().startswith("SELECT C.COUNTRY")
        assert rows[0]["question"] == "revenue by country"

    def test_history_is_per_session_and_shown_to_the_model(self, page):
        at, script, _ = page
        model = script("first answer", "second answer")
        at.run()
        ask(at, "first")
        ask(at, "second")
        assert at.session_state["history"] == [("first", "first answer"), ("second", "second answer")]
        second_call_contents = [getattr(m, "content", "") for m in model.seen[1]]
        assert "first answer" in second_call_contents

    def test_a_write_requested_by_the_model_shows_as_refused_in_the_steps(self, page):
        at, script, _ = page
        script([("run_query", {"sql": "DELETE FROM orders"})], "I cannot modify data.")
        at.run()
        ask(at, "delete everything")
        assert any("refused" in el.value for el in at.code)

    def test_no_model_key_stops_before_calling_anything(self, page, monkeypatch):
        at, script, _ = page
        model = script("should not be reached")
        monkeypatch.setattr(settings, "LLM_API_KEY", "")
        at.run()
        ask(at, "anything")
        assert any("LLM_API_KEY" in el.value for el in at.error)
        assert model.seen == []


class TestCsvSafety:
    @pytest.mark.parametrize("value", ["=HYPERLINK(1)", "+1", "-1", "@cmd"])
    def test_formula_prefixes_are_neutralised(self, value):
        from app import csv_safe

        assert csv_safe(value).startswith("'")

    def test_ordinary_text_is_untouched(self):
        from app import csv_safe

        assert csv_safe("hello") == "hello"
