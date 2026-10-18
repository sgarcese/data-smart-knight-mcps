"""Pure parsing/aggregation of the structured JSON Lambda log lines.

No AWS calls here — these functions take raw ``@message`` strings and turn
them into dashboard-ready summaries. Kept separate from ``cloudwatch.py`` so
the aggregation logic is unit-testable without live AWS access.

Field shapes below were confirmed against real production log lines (not
just the source in ``core/logging_utils.py``/``core/mcp_server.py``) — the
``core.mcp_server`` logger emits ``jsonrpc_method``/``jsonrpc_params``/
``jsonrpc_error`` as clean top-level JSON fields per JSON-RPC call, which is
simpler to key off than the HTTP-layer's nested ``request_body``/
``response_body`` (used by ``server/http_handler.py``, still present in logs
but redundant with the mcp_server-level fields for this dashboard's needs):

    {"message": "JSON-RPC request received", "jsonrpc_method": "tools/call",
     "jsonrpc_params": {"name": "socrata__query_dataset", "arguments": {...}}, ...}

    {"message": "JSON-RPC request processed successfully",
     "jsonrpc_method": "tools/call", "duration_ms": 288.75,
     "jsonrpc_result": {...}, "success": true, ...}

    {"message": "Error handling JSON-RPC request ...", "levelname": "ERROR",
     "jsonrpc_method": "server/discover", "duration_ms": 0.17,
     "jsonrpc_error": {"code": -32603, "message": "...", "data": "..."},
     "success": false, "error_type": "ValueError", ...}
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

# Passed to cloudwatch.fetch_log_messages() as the Logs Insights `filter` clause.
TOOL_USAGE_FILTER = '@message like /"JSON-RPC request received"/'
ERRORS_FILTER = '@message like /"success": false/'
# Scoped to the mcp_server-layer "one row per JSON-RPC call" lines (both have
# jsonrpc_method + duration_ms) so we don't double-count against the
# HTTP-layer's own duration_ms for the same request.
DURATION_FILTER = '@message like /"jsonrpc_method"/ and @message like /"duration_ms"/'


def _parse_lines(messages: list[str]) -> list[dict[str, Any]]:
    parsed = []
    for msg in messages:
        try:
            parsed.append(json.loads(msg))
        except (json.JSONDecodeError, TypeError):
            continue
    return parsed


def tool_usage_breakdown(messages: list[str]) -> Counter:
    """Count JSON-RPC calls by method, and by tool name for ``tools/call``.

    Keyed on a display label: the bare method name (e.g. "initialize",
    "tools/list"), or "tools/call: <tool_name>" for tool invocations.
    """
    counts: Counter = Counter()
    for record in _parse_lines(messages):
        if record.get("message") != "JSON-RPC request received":
            continue
        method = record.get("jsonrpc_method")
        if not method:
            continue
        if method == "tools/call":
            tool_name = (record.get("jsonrpc_params") or {}).get("name", "unknown")
            counts[f"tools/call: {tool_name}"] += 1
        else:
            counts[method] += 1
    return counts


def recent_errors(messages: list[str], limit: int = 50) -> list[dict[str, Any]]:
    """Extract failed requests (``success is False``) as flat summary rows."""
    rows = []
    for record in _parse_lines(messages):
        if record.get("success") is not False:
            continue
        rows.append(
            {
                "timestamp": record.get("asctime") or record.get("timestamp"),
                "request_id": record.get("request_id") or record.get("jsonrpc_request_id"),
                "method": record.get("jsonrpc_method"),
                "error_type": record.get("error_type"),
                "duration_ms": record.get("duration_ms"),
                "detail": record.get("jsonrpc_error") or record.get("response_body"),
            }
        )
    rows.sort(key=lambda r: r["timestamp"] or "", reverse=True)
    return rows[:limit]


def slowest_requests(messages: list[str], limit: int = 20) -> list[dict[str, Any]]:
    """Rank completed JSON-RPC calls (success or failure) by ``duration_ms`` descending."""
    rows = []
    for record in _parse_lines(messages):
        if "duration_ms" not in record or "jsonrpc_method" not in record:
            continue
        rows.append(
            {
                "timestamp": record.get("asctime") or record.get("timestamp"),
                "request_id": record.get("jsonrpc_request_id"),
                "method": record.get("jsonrpc_method"),
                "success": record.get("success"),
                "duration_ms": record.get("duration_ms"),
            }
        )
    rows.sort(key=lambda r: r["duration_ms"] or 0, reverse=True)
    return rows[:limit]
