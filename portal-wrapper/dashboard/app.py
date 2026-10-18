"""Streamlit dashboard for comparing usage/health across Responsive Cities MCP portals.

Run locally with an AWS profile that can read the target account:

    AWS_PROFILE=rc-deploy streamlit run app.py

Read-only — never writes to AWS. See README.md for the IAM actions it needs.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from cloudwatch import fetch_log_messages, get_lambda_metrics
from log_analysis import (
    DURATION_FILTER,
    ERRORS_FILTER,
    TOOL_USAGE_FILTER,
    recent_errors,
    slowest_requests,
    tool_usage_breakdown,
)
from portals import Portal, discover_portal_functions

st.set_page_config(page_title="MCP Portal Usage", layout="wide")

TIME_RANGES = {
    "Last hour": timedelta(hours=1),
    "Last 24 hours": timedelta(hours=24),
    "Last 7 days": timedelta(days=7),
}


@st.cache_data(ttl=300)
def _discover(env: str) -> list[Portal]:
    return discover_portal_functions(env)


@st.cache_data(ttl=300)
def _metrics(function_names: tuple[str, ...], start: datetime, end: datetime):
    return get_lambda_metrics(list(function_names), start, end)


@st.cache_data(ttl=300)
def _log_messages(log_group: str, start: datetime, end: datetime, filter_pattern: str, limit: int):
    return fetch_log_messages(log_group, start, end, filter_pattern=filter_pattern, limit=limit)


st.title("Responsive Cities MCP — Portal Usage")

with st.sidebar:
    env = st.selectbox("Environment", ["prod", "staging", "dev"], index=0)
    range_label = st.selectbox("Time range", list(TIME_RANGES.keys()), index=1)
    st.caption("Reads CloudWatch directly with your local AWS credentials. Nothing is written or deployed.")

end = datetime.now(timezone.utc)
start = end - TIME_RANGES[range_label]

portals = _discover(env)
if not portals:
    st.warning(f"No Lambda functions found matching `rc-*-mcp-{env}`. Wrong profile/region, or nothing deployed yet?")
    st.stop()

portal_by_slug = {p.slug: p for p in portals}
default_slugs = [p.slug for p in portals]
selected_slugs = st.sidebar.multiselect(
    "Portals", options=default_slugs, default=default_slugs, format_func=lambda s: portal_by_slug[s].city
)
selected = [portal_by_slug[s] for s in selected_slugs] or portals

st.caption(f"{len(selected)} of {len(portals)} portals · {env} · {range_label.lower()} (UTC {start:%H:%M} – {end:%H:%M})")

# --- Comparison: invocations / errors / latency -----------------------------
st.header("Usage comparison")

metrics = _metrics(tuple(p.function_name for p in selected), start, end)
rows = []
for p in selected:
    m = metrics.get(p.function_name, {})
    invocations = m.get("invocations", 0.0)
    errors = m.get("errors", 0.0)
    rows.append(
        {
            "Portal": p.city,
            "Invocations": int(invocations),
            "Errors": int(errors),
            "Error rate": (errors / invocations) if invocations else 0.0,
            "Throttles": int(m.get("throttles", 0.0)),
            "Avg duration (ms)": round(m.get("duration_avg_ms", 0.0), 1),
            "p50 duration (ms)": round(m.get("duration_p50_ms", 0.0), 1),
            "p95 duration (ms)": round(m.get("duration_p95_ms", 0.0), 1),
        }
    )
df = pd.DataFrame(rows).sort_values("Invocations", ascending=False)

st.dataframe(
    df,
    column_config={"Error rate": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=1)},
    hide_index=True,
    width="stretch",
)
st.bar_chart(df.set_index("Portal")[["Invocations", "Errors"]])

# --- Tool usage breakdown -----------------------------------------------------
st.header("Tool / method usage")

tool_rows = []
with st.spinner("Querying CloudWatch Logs Insights for tool usage…"):
    for p in selected:
        messages = _log_messages(p.log_group, start, end, TOOL_USAGE_FILTER, 1000)
        for label, count in tool_usage_breakdown(messages).items():
            tool_rows.append({"Portal": p.city, "Method": label, "Calls": count})

if tool_rows:
    tool_df = pd.DataFrame(tool_rows)
    pivot = tool_df.pivot_table(index="Portal", columns="Method", values="Calls", fill_value=0, aggfunc="sum")
    st.bar_chart(pivot)
    with st.expander("Raw counts"):
        st.dataframe(tool_df.sort_values(["Portal", "Calls"], ascending=[True, False]), hide_index=True, width="stretch")
else:
    st.info("No requests found in this window for the selected portals.")

# --- Recent errors -------------------------------------------------------------
st.header("Recent errors")

error_rows = []
with st.spinner("Querying CloudWatch Logs Insights for errors…"):
    for p in selected:
        messages = _log_messages(p.log_group, start, end, ERRORS_FILTER, 500)
        for row in recent_errors(messages, limit=20):
            error_rows.append({"Portal": p.city, **row})

if error_rows:
    error_df = pd.DataFrame(error_rows).sort_values("timestamp", ascending=False)
    for _, row in error_df.iterrows():
        with st.expander(f"{row['Portal']} · {row['timestamp']} · {row['method'] or ''} · {row['error_type'] or ''}"):
            st.json(row["detail"])
else:
    st.success("No errors in this window for the selected portals.")

# --- Slowest requests ------------------------------------------------------------
st.header("Slowest requests")

slow_rows = []
with st.spinner("Querying CloudWatch Logs Insights for request durations…"):
    for p in selected:
        messages = _log_messages(p.log_group, start, end, DURATION_FILTER, 2000)
        for row in slowest_requests(messages, limit=10):
            slow_rows.append({"Portal": p.city, **row})

if slow_rows:
    slow_df = pd.DataFrame(slow_rows).sort_values("duration_ms", ascending=False).head(50)
    st.dataframe(slow_df, hide_index=True, width="stretch")
else:
    st.info("No completed requests found in this window for the selected portals.")
