"""
The Streamlit page.

Four things the previous page did that mattered:

* The agent was ``@st.cache_resource`` -- one object for the whole server --
  and it kept the conversation history on itself. Every user of the server
  shared one conversation. History now lives in ``st.session_state``.
* The "Correct / Incorrect" buttons were rendered inside ``if run_query:``.
  Clicking one reruns the script, ``run_query`` is False on that rerun, the
  block is not rendered, and the click is lost. They never logged anything.
  The last answer is kept in session state and the buttons render from it.
* The feedback row logged ``"N/A"`` as the SQL, unconditionally.
* The sidebar showed "DeepSeek-V3: Online", "Security: Row-Level Active" and
  "Schema Cache: Active" as static text. Nothing checked the model, nothing
  implemented row-level security, and there was no schema cache. The sidebar
  now shows what is actually checked.

It also re-ran the model's last SQL through a second, read-write engine with
no guard to build the chart. The chart is built from the rows the agent
already fetched.
"""

from __future__ import annotations

import csv
import logging
import os
from datetime import UTC, datetime

import pandas as pd
import sqlalchemy
import streamlit as st

from agent import Answer, SQLAgent
from config import settings
from db import redacted
from llm import LLMNotConfigured
from setup_db import create_sample_database
from visualizer import auto_visualize, summary_stats

logging.basicConfig(level=settings.LOG_LEVEL)

st.set_page_config(page_title="SQL Agent", page_icon="🗄️", layout="wide")

EXAMPLES = [
    ("Monthly revenue", "Show total sales (total_amount) by month for the last 6 months."),
    ("Revenue by country", "What is the total revenue per country?"),
    ("Top customers", "Who are the top 5 customers by total spending?"),
    ("Category prices", "Which product categories have the highest and lowest average prices?"),
    ("Recent orders", "List the 10 most recent orders with customer name and product name."),
]


# -- setup ----------------------------------------------------------------------


def ensure_sample_database() -> None:
    """Create the bundled SQLite sample if the configured URL points at a missing file."""
    url = settings.DATABASE_URL
    if url.startswith("sqlite:///") and not url.startswith("sqlite:///file:"):
        path = url[len("sqlite:///") :]
        if path and path != ":memory:" and not os.path.exists(path):
            with st.status("Creating the sample database…"):
                create_sample_database(path)


@st.cache_resource
def get_agent() -> SQLAgent:
    return SQLAgent(settings.DATABASE_URL)


def csv_safe(value: object) -> str:
    """Neutralise spreadsheet formula injection: a cell starting with = + - @ is quoted."""
    text = str(value if value is not None else "")
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text


def log_feedback(question: str, sql: str | None, answer: str, verdict: str) -> bool:
    path = settings.FEEDBACK_PATH
    if not path:
        return False
    new = not os.path.isfile(path)
    with open(path, "a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        if new:
            writer.writerow(["timestamp", "question", "sql", "answer", "verdict"])
        writer.writerow(
            [
                datetime.now(UTC).isoformat(),
                csv_safe(question),
                csv_safe(sql or ""),
                csv_safe(answer),
                verdict,
            ]
        )
    return True


def connection_status(agent: SQLAgent) -> dict[str, tuple[bool, str]]:
    """What is actually true about this instance. Each entry is (ok, detail)."""
    checks: dict[str, tuple[bool, str]] = {}
    try:
        with agent.engine.connect() as conn:
            conn.execute(sqlalchemy.text("SELECT 1"))
        checks["database"] = (True, redacted(settings.DATABASE_URL))
    except Exception as error:
        checks["database"] = (False, f"unreachable: {type(error).__name__}")
    checks["connection mode"] = (True, "read-only (mode=ro / default_transaction_read_only)")
    checks["model"] = (
        settings.has_llm_key,
        f"{settings.LLM_MODEL} via {settings.LLM_BASE_URL}"
        if settings.has_llm_key
        else "LLM_API_KEY not set",
    )
    checks["row limit"] = (True, str(settings.MAX_ROWS))
    return checks


# -- state ------------------------------------------------------------------------

st.session_state.setdefault("history", [])  # list of (question, answer) for THIS session
st.session_state.setdefault("last", None)  # (question, Answer)
st.session_state.setdefault("question", "")

ensure_sample_database()

try:
    agent = get_agent()
except Exception as error:  # a bad DATABASE_URL, an unsupported backend
    st.error(f"The agent could not start: {type(error).__name__}: {error}")
    st.stop()


# -- sidebar ------------------------------------------------------------------------

with st.sidebar:
    st.title("SQL Agent")
    st.caption("Ask questions in plain language; the agent writes and runs read-only SQL.")

    st.subheader("Status")
    for name, (ok, detail) in connection_status(agent).items():
        (st.success if ok else st.error)(f"{name}: {detail}")

    st.subheader("Examples")
    for label, text in EXAMPLES:
        if st.button(label, use_container_width=True, key=f"ex_{label}"):
            st.session_state.question = text

    if st.session_state.history:
        st.subheader("This session")
        for index, (past_q, _) in enumerate(reversed(st.session_state.history)):
            if st.button(f"↺ {past_q[:40]}", key=f"hist_{index}", use_container_width=True):
                st.session_state.question = past_q
        if st.button("Clear session history", use_container_width=True):
            st.session_state.history = []
            st.session_state.last = None
            st.rerun()


# -- main ---------------------------------------------------------------------------

st.title("Ask the database")

question = st.text_area(
    "Question",
    value=st.session_state.question,
    placeholder="e.g. Compare average order value between USA and UK",
    height=90,
    key="question_input",
)

run = st.button("Run", type="primary")

if run and question.strip():
    if not settings.has_llm_key:
        st.error("LLM_API_KEY is not set. Add it to .env (DEEPSEEK_API_KEY is accepted as an alias).")
    else:
        with st.spinner("Working…"):
            try:
                answer = agent.ask(question, st.session_state.history)
            except LLMNotConfigured as error:
                st.error(str(error))
                answer = None
            except Exception as error:
                logging.getLogger("sql_agent.app").exception("agent failed")
                st.error(f"The agent failed: {type(error).__name__}. Details are in the server log.")
                answer = None
        if answer is not None:
            st.session_state.last = (question, answer)
            st.session_state.history.append((question, answer.text))
            st.session_state.history = st.session_state.history[-20:]

# Rendered from session state, so it survives the reruns that button clicks cause.
if st.session_state.last:
    asked, answer = st.session_state.last
    assert isinstance(answer, Answer)

    st.subheader("Answer")
    st.write(answer.text)
    if answer.stopped_early:
        st.warning("The agent hit its step limit before a final answer.")

    col_ok, col_bad, _ = st.columns([1, 1, 4])
    with col_ok:
        if st.button("👍 Correct", key="fb_ok") and log_feedback(asked, answer.sql, answer.text, "correct"):
            st.toast("Feedback saved.")
    with col_bad:
        if st.button("👎 Incorrect", key="fb_bad") and log_feedback(
            asked, answer.sql, answer.text, "incorrect"
        ):
            st.toast("Feedback saved.")

    tab_data, tab_chart, tab_steps = st.tabs(["Data", "Chart", "Steps"])

    with tab_data:
        if answer.result and answer.result.rows:
            df = pd.DataFrame(answer.result.rows, columns=answer.result.columns)
            st.dataframe(df, use_container_width=True)
            if answer.result.truncated:
                st.caption(f"Showing the first {settings.MAX_ROWS} rows; the result was capped.")
            st.code(answer.sql or "", language="sql")
        else:
            st.info("No result set. The answer above came from the agent's text, not from rows.")

    with tab_chart:
        if answer.result and answer.result.rows:
            df = pd.DataFrame(answer.result.rows, columns=answer.result.columns)
            fig = auto_visualize(df, title=asked[:60])
            if fig is not None:
                st.plotly_chart(fig, use_container_width=True)
            st.code(summary_stats(df), language="text")
        else:
            st.info("Nothing to chart.")

    with tab_steps:
        if not answer.steps:
            st.info("The model answered without using a tool.")
        for index, step in enumerate(answer.steps, 1):
            with st.expander(
                f"{index}. {step.tool}({', '.join(f'{k}={v!r}' for k, v in step.args.items())})"
            ):
                st.code(step.observation, language="text")

st.caption("Every number shown comes from a query the agent ran on a read-only connection.")
