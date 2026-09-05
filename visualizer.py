"""
Pick a chart for a result set.

``auto_visualize`` used to rename the columns of the DataFrame it was given
(``df.columns = [...]``) as a side effect, so the "source data" tab and the
summary the caller rendered afterwards showed different column names from
the query. It works on a copy now. The bare ``except:`` around date parsing
and the ``print`` of chart errors are gone.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd
import plotly.express as px

logger = logging.getLogger("sql_agent.visualizer")

COLORS = ["#00f2ff", "#7000ff", "#ff007a", "#00ffab", "#ffea00"]
DATE_HINTS = ("date", "time", "month", "day", "year")


def should_visualize(df: pd.DataFrame) -> bool:
    if df.empty or len(df) < 2:
        return False
    return len(df.select_dtypes(include=["number"]).columns) > 0


def _display_name(column: str) -> str:
    return column.replace("_", " ").title()


def auto_visualize(df: pd.DataFrame, title: str = "Results") -> Any | None:
    """A plotly figure, or ``None`` when the frame has nothing to chart."""
    if not should_visualize(df):
        return None

    frame = df.copy()
    frame.columns = [_display_name(c) for c in frame.columns]

    numeric = frame.select_dtypes(include=["number"]).columns.tolist()
    categorical = frame.select_dtypes(include=["object", "category"]).columns.tolist()

    dates: list[str] = []
    for column in categorical:
        if any(hint in column.lower() for hint in DATE_HINTS):
            try:
                frame[column] = pd.to_datetime(frame[column])
                dates.append(column)
            except (ValueError, TypeError):
                continue
    categorical = [c for c in categorical if c not in dates]

    try:
        if dates and numeric:
            fig = px.line(frame, x=dates[0], y=numeric[0], title=title, color_discrete_sequence=COLORS)
            fig.update_traces(line={"width": 3})
        elif categorical and numeric:
            if len(frame) <= 5 and len(numeric) == 1:
                fig = px.pie(
                    frame,
                    names=categorical[0],
                    values=numeric[0],
                    title=title,
                    hole=0.4,
                    color_discrete_sequence=COLORS,
                )
            else:
                fig = px.bar(
                    frame, x=categorical[0], y=numeric[0], title=title, color_discrete_sequence=COLORS
                )
        elif len(numeric) >= 2:
            fig = px.scatter(frame, x=numeric[0], y=numeric[1], title=title, color_discrete_sequence=COLORS)
        else:
            fig = px.bar(frame, y=numeric[0], title=title, color_discrete_sequence=COLORS)
    except Exception:
        logger.exception("could not build a chart")
        return None

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin={"l": 40, "r": 40, "t": 60, "b": 40},
    )
    return fig


def summary_stats(df: pd.DataFrame) -> str:
    """Sum and mean of each numeric column. Money-like columns are formatted as amounts."""
    numeric = df.select_dtypes(include=["number"])
    if numeric.empty:
        return f"{len(df)} row(s), no numeric columns."
    lines = [f"{len(df)} row(s)"]
    for column in numeric.columns:
        total = numeric[column].sum()
        mean = numeric[column].mean()
        money = any(hint in column.lower() for hint in ("price", "amount", "total", "revenue"))
        if money:
            lines.append(f"- {_display_name(column)}: total {total:,.2f}, mean {mean:,.2f}")
        else:
            lines.append(f"- {_display_name(column)}: sum {total:,.0f}, mean {mean:,.1f}")
    return "\n".join(lines)
