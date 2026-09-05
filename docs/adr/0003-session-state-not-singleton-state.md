# ADR 0003 — Conversation and results live in session state; status is measured

**Status:** accepted

## Context

The page held the agent in `@st.cache_resource` — one object per server —
and the agent kept `self.history`. Every visitor shared one conversation.

The feedback buttons were rendered inside `if run_query and user_q:`. A click
reruns the script with `run_query` false, so the block that contains the
buttons is not rendered on that run and the click is never handled. They
could not log anything. When they would have, they logged the SQL as `"N/A"`.

The sidebar displayed "DeepSeek-V3: Online", "Security: Row-Level Active"
and "Schema Cache: Active" as static text. Nothing checked the model, nothing
implemented row-level security, and there was no schema cache.

## Decision

- `st.session_state.history` holds the session's turns and is passed to
  `agent.ask()`; the agent keeps nothing between calls.
- The last answer is stored in session state and rendered from it, so the
  feedback buttons exist on the rerun a click causes. Feedback records the
  question, the SQL that produced the answer, the answer and the verdict.
  Cells beginning with `= + - @` are prefixed with `'` so a spreadsheet does
  not evaluate them.
- The sidebar shows measured facts: a `SELECT 1` against the engine, the
  read-only mode in force, whether a model key is configured and which
  endpoint it points at, the row limit.

## Consequences

Two users of one server see their own conversations. The AppTest suite
drives the page headlessly and asserts the feedback file's contents.
