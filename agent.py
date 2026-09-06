"""
The SQL agent: a bounded tool-calling loop.

The previous agent was ``create_sql_agent(..., agent_type="zero-shot-react-description")``
from ``langchain_community`` -- the legacy AgentExecutor path, with the stock
toolkit's read-write query tool, an unbounded step count, and a question-level
keyword filter (``"delete" in question.lower()``) as its only guard. The
filter refused "which products were updated last month?" and admitted
"remove every row from orders".

This loop owns its tools. The model sees three: ``list_tables``,
``describe_table`` and ``run_query``; the last one runs only what
``sql_guard`` admits, on a read-only connection, and its result is kept as
data so the page never re-executes the statement.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from config import settings
from db import read_only_engine
from llm import get_chat_model
from tools import QueryResult, SQLTools

logger = logging.getLogger("sql_agent.agent")

SYSTEM_PROMPT = """You are a careful SQL data analyst.

You have three tools. Use list_tables and describe_table before writing a query
against a table you have not seen. Then use run_query with exactly one SELECT
statement. You cannot modify data; the connection is read-only and non-SELECT
statements are refused.

When you have the answer, reply in plain language: what the numbers say and,
in one sentence, what you assumed if the question was ambiguous. Do not invent
figures; only report what run_query returned."""

TOOL_SPECS = [
    {
        "name": "list_tables",
        "description": "List the tables in the database.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "describe_table",
        "description": "Columns, types and sample rows for one table.",
        "parameters": {
            "type": "object",
            "properties": {"table": {"type": "string", "description": "table name"}},
            "required": ["table"],
        },
    },
    {
        "name": "run_query",
        "description": "Run one read-only SELECT statement and return its rows.",
        "parameters": {
            "type": "object",
            "properties": {"sql": {"type": "string", "description": "a single SELECT statement"}},
            "required": ["sql"],
        },
    },
]


@dataclass
class Step:
    tool: str
    args: dict[str, Any]
    observation: str


@dataclass
class Answer:
    text: str
    sql: str | None = None
    result: QueryResult | None = None
    steps: list[Step] = field(default_factory=list)
    stopped_early: bool = False


class SQLAgent:
    def __init__(
        self,
        database_url: str | None = None,
        *,
        model: Any = None,
        max_steps: int = 8,
        max_rows: int | None = None,
    ) -> None:
        url = database_url or settings.DATABASE_URL
        self.engine = read_only_engine(url)
        self.tools = SQLTools(self.engine, max_rows=max_rows or settings.MAX_ROWS)
        self._model = model
        self.max_steps = max_steps

    @property
    def model(self) -> Any:
        if self._model is None:
            self._model = get_chat_model()
        return self._model

    # -- schema helpers for the page ----------------------------------------

    def table_names(self) -> list[str]:
        return [t.strip() for t in self.tools.list_tables().split(",") if t.strip() and t != "(no tables)"]

    # -- the loop -------------------------------------------------------------

    def ask(self, question: str, history: list[tuple[str, str]] | None = None) -> Answer:
        """
        Answer ``question`` using the tools, with the last few turns as context.

        ``history`` belongs to the caller's session. The previous agent kept
        it on the object -- which the page cached as a singleton, so every
        user of the server shared one conversation.
        """
        question = (question or "").strip()
        if not question:
            return Answer(text="Ask a question about the data.")

        messages: list[Any] = [SystemMessage(content=SYSTEM_PROMPT)]
        for past_q, past_a in (history or [])[-settings.HISTORY_TURNS :]:
            messages.append(HumanMessage(content=past_q))
            messages.append(AIMessage(content=past_a))
        messages.append(HumanMessage(content=question))

        bound = self.model.bind_tools(TOOL_SPECS)
        self.tools.last_result = None
        steps: list[Step] = []
        last_query: QueryResult | None = None

        for _ in range(self.max_steps):
            reply = bound.invoke(messages)
            calls = getattr(reply, "tool_calls", None) or []
            if not calls:
                return Answer(
                    text=_text(reply),
                    sql=last_query.sql if last_query and last_query.ok else None,
                    result=last_query if last_query and last_query.ok else None,
                    steps=steps,
                )
            messages.append(reply)
            for call in calls:
                observation = self._dispatch(call["name"], call.get("args") or {})
                steps.append(Step(call["name"], call.get("args") or {}, observation))
                if call["name"] == "run_query" and self.tools.last_result is not None:
                    last_query = self.tools.last_result
                messages.append(ToolMessage(content=observation, tool_call_id=call.get("id") or call["name"]))

        logger.warning("agent stopped after %d steps without a final answer", self.max_steps)
        return Answer(
            text=f"I stopped after {self.max_steps} tool calls without reaching an answer. "
            "Try a narrower question.",
            sql=last_query.sql if last_query and last_query.ok else None,
            result=last_query if last_query and last_query.ok else None,
            steps=steps,
            stopped_early=True,
        )

    def _dispatch(self, name: str, args: dict[str, Any]) -> str:
        try:
            if name == "list_tables":
                return self.tools.list_tables()
            if name == "describe_table":
                return self.tools.describe_table(str(args.get("table", "")))
            if name == "run_query":
                return self.tools.run_query(str(args.get("sql", ""))).as_text()
        except Exception as error:  # the model must see a message, not a traceback
            logger.exception("tool %s failed", name)
            return f"ERROR: {type(error).__name__} while running {name}"
        return f"ERROR: unknown tool {name!r}; available: list_tables, describe_table, run_query"


def _text(message: Any) -> str:
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [b.get("text", "") if isinstance(b, dict) else str(b) for b in content]
        return "".join(parts)
    return json.dumps(content) if not isinstance(content, str) else content
