"""
Shared fixtures.

No test reaches a network or needs a model key. The agent is driven by a
scripted model that returns the tool calls a test specifies.
"""

from __future__ import annotations

import os
import sqlite3

import pytest

os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("LLM_API_KEY", "test-key-not-real")
os.environ.setdefault("FEEDBACK_PATH", "")

from langchain_core.messages import AIMessage

from llm import set_model_factory
from setup_db import create_sample_database


@pytest.fixture
def sample_db(tmp_path):
    """The bundled sample database, deterministic, in a temp dir. Returns its sqlite URL."""
    path = tmp_path / "ecommerce.db"
    create_sample_database(str(path), seed=1)
    return f"sqlite:///{path}"


@pytest.fixture
def tiny_db(tmp_path):
    """A two-row table for write-refusal tests."""
    path = tmp_path / "tiny.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, created_at TEXT)")
    conn.execute("INSERT INTO customers VALUES (1, 'a', '2026-01-01'), (2, 'b', '2026-02-01')")
    conn.commit()
    conn.close()
    return f"sqlite:///{path}"


class ScriptedModel:
    """
    A chat model that replays a script of replies.

    Each entry is either a string (a final answer) or a list of
    ``(tool_name, args)`` tuples (tool calls). ``bind_tools`` returns self so
    the agent's loop runs unchanged.
    """

    def __init__(self, script):
        self.script = list(script)
        self.seen = []
        self.bound_tools = None

    def bind_tools(self, tools):
        self.bound_tools = tools
        return self

    def invoke(self, messages):
        self.seen.append(list(messages))
        if not self.script:
            return AIMessage(content="(script exhausted)")
        entry = self.script.pop(0)
        if isinstance(entry, str):
            return AIMessage(content=entry)
        calls = [
            {"name": name, "args": args, "id": f"call-{index}"} for index, (name, args) in enumerate(entry)
        ]
        return AIMessage(content="", tool_calls=calls)


@pytest.fixture
def scripted():
    def build(*entries):
        model = ScriptedModel(entries)
        set_model_factory(lambda: model)
        return model

    yield build
    set_model_factory(None)


@pytest.fixture(autouse=True)
def _reset_factory():
    yield
    set_model_factory(None)
