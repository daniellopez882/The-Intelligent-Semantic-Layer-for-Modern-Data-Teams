# ADR 0002 — The agent owns its tools; the loop is small and bounded

**Status:** accepted

## Context

`create_sql_agent(agent_type="zero-shot-react-description")` from
`langchain_community` is the legacy AgentExecutor path: deprecated upstream,
dependent on whichever `langchain` version an unconstrained `requirements.txt`
happens to resolve, and not something this repository controls. The stock
toolkit it brought had its own read-write query tool (ADR 0001) and the loop
had no step bound.

## Decision

`agent.py` is a tool-calling loop over `langchain-core` only: the model is
bound to three tool specifications — `list_tables`, `describe_table`,
`run_query` — and invoked until it answers without a tool call or reaches
`max_steps`. Tool results are returned as data (`QueryResult`) and the last
successful query is kept for the page.

`llm.get_chat_model()` builds the one supported provider — any
OpenAI-compatible endpoint, DeepSeek by default — from configuration, and
`set_model_factory` is the seam the tests use with a scripted model.

## Consequences

The runtime dependencies are `langchain-core`, `langchain-openai`,
`sqlalchemy`, `sqlglot`, `pandas`, `plotly`, `streamlit`, `pydantic-settings`.
`langchain`, `langchain-community`, `langchain-anthropic`, `duckdb` and
`openai` (direct) are gone: nothing imported them.

The loop is testable without a key: the agent tests run with scripted tool
calls, including a model that asks for a DELETE and a model that never stops.
