"""
The tool-calling loop, driven by a scripted model.

The original test file needed a live DeepSeek key and wrapped everything in
``try/except: print``; pytest collected it and it passed with no key at all.
"""

from __future__ import annotations

import pytest

from agent import SQLAgent
from llm import LLMNotConfigured


def agent_for(url, scripted, *script, **kwargs):
    model = scripted(*script)
    return SQLAgent(url, model=model, **kwargs), model


class TestHappyPath:
    def test_the_agent_answers_from_a_query(self, sample_db, scripted):
        agent, _ = agent_for(
            sample_db,
            scripted,
            [("list_tables", {})],
            [("run_query", {"sql": "SELECT COUNT(*) AS n FROM customers"})],
            "There are 40 customers.",
        )
        answer = agent.ask("How many customers are there?")
        assert answer.text == "There are 40 customers."
        assert answer.result.rows == [{"n": 40}]
        assert "LIMIT" in answer.sql.upper()
        assert [s.tool for s in answer.steps] == ["list_tables", "run_query"]

    def test_the_model_sees_the_three_tools(self, sample_db, scripted):
        agent, model = agent_for(sample_db, scripted, "hi")
        agent.ask("x")
        assert {t["name"] for t in model.bound_tools} == {"list_tables", "describe_table", "run_query"}

    def test_tool_observations_are_fed_back(self, sample_db, scripted):
        agent, model = agent_for(sample_db, scripted, [("list_tables", {})], "done")
        agent.ask("x")
        last_messages = model.seen[-1]
        assert any("customers" in getattr(m, "content", "") for m in last_messages)

    def test_history_is_passed_from_the_caller(self, sample_db, scripted):
        """History belongs to the session, not the agent object."""
        agent, model = agent_for(sample_db, scripted, "ok")
        agent.ask("second", history=[("first question", "first answer")])
        contents = [getattr(m, "content", "") for m in model.seen[0]]
        assert "first question" in contents and "first answer" in contents

    def test_history_is_capped(self, sample_db, scripted, monkeypatch):
        from config import settings

        monkeypatch.setattr(settings, "HISTORY_TURNS", 2)
        agent, model = agent_for(sample_db, scripted, "ok")
        agent.ask("q", history=[(f"q{i}", f"a{i}") for i in range(10)])
        contents = [getattr(m, "content", "") for m in model.seen[0]]
        assert "q9" in contents and "q7" not in contents


class TestSafety:
    def test_a_write_requested_by_the_model_is_refused_and_reported(self, tiny_db, scripted):
        agent, _ = agent_for(
            tiny_db,
            scripted,
            [("run_query", {"sql": "DELETE FROM customers"})],
            "I could not do that.",
        )
        answer = agent.ask("remove every row from customers")
        assert answer.sql is None
        assert "refused" in answer.steps[0].observation
        assert agent.tools.run_query("SELECT COUNT(*) AS n FROM customers").rows[0]["n"] == 2

    def test_the_connection_itself_is_read_only(self, tiny_db, scripted):
        import sqlalchemy

        agent, _ = agent_for(tiny_db, scripted, "x")
        with pytest.raises(sqlalchemy.exc.SQLAlchemyError), agent.engine.begin() as conn:
            conn.execute(sqlalchemy.text("DELETE FROM customers"))

    def test_the_loop_is_bounded(self, sample_db, scripted):
        agent, _ = agent_for(sample_db, scripted, *([[("list_tables", {})]] * 50), max_steps=4)
        answer = agent.ask("loop forever")
        assert answer.stopped_early is True
        assert len(answer.steps) == 4

    def test_an_unknown_tool_name_is_reported_to_the_model(self, sample_db, scripted):
        agent, _ = agent_for(sample_db, scripted, [("drop_everything", {})], "ok")
        answer = agent.ask("x")
        assert "unknown tool" in answer.steps[0].observation

    def test_a_tool_exception_becomes_an_observation(self, sample_db, scripted, monkeypatch):
        agent, _ = agent_for(sample_db, scripted, [("list_tables", {})], "ok")

        def boom():
            raise RuntimeError("disk on fire")

        monkeypatch.setattr(agent.tools, "list_tables", boom)
        answer = agent.ask("x")
        assert answer.steps[0].observation.startswith("ERROR: RuntimeError")
        assert "disk on fire" not in answer.steps[0].observation


class TestEdges:
    def test_an_empty_question_does_not_call_the_model(self, sample_db, scripted):
        agent, model = agent_for(sample_db, scripted, "should not be used")
        assert "Ask a question" in agent.ask("   ").text
        assert model.seen == []

    def test_no_model_key_names_the_setting(self, sample_db, monkeypatch):
        from config import settings

        monkeypatch.setattr(settings, "LLM_API_KEY", "")
        with pytest.raises(LLMNotConfigured, match="LLM_API_KEY"):
            SQLAgent(sample_db).ask("x")

    def test_table_names_helper(self, sample_db, scripted):
        agent, _ = agent_for(sample_db, scripted, "x")
        assert set(agent.table_names()) == {"customers", "orders", "products"}
