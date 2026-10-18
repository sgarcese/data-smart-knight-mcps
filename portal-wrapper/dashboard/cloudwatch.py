"""CloudWatch Metrics + Logs Insights access for the MCP usage dashboard."""

from __future__ import annotations

import time
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

_METRIC_SPECS = (
    # (result key, MetricName, Stat)
    ("invocations", "Invocations", "Sum"),
    ("errors", "Errors", "Sum"),
    ("throttles", "Throttles", "Sum"),
    ("duration_avg_ms", "Duration", "Average"),
    ("duration_p50_ms", "Duration", "p50"),
    ("duration_p95_ms", "Duration", "p95"),
)


def _pick_period(start: datetime, end: datetime) -> int:
    """Pick a CloudWatch period (seconds) that keeps the datapoint count sane."""
    seconds = (end - start).total_seconds()
    if seconds <= 3 * 3600:
        return 60
    if seconds <= 24 * 3600:
        return 300
    if seconds <= 7 * 24 * 3600:
        return 3600
    return 86400


def get_lambda_metrics(
    function_names: list[str], start: datetime, end: datetime
) -> dict[str, dict[str, float]]:
    """Fetch AWS/Lambda invocation/error/duration metrics for each function.

    Returns ``{function_name: {"invocations": n, "errors": n, "throttles": n,
    "duration_avg_ms": x, "duration_p50_ms": x, "duration_p95_ms": x}}``.
    """
    if not function_names:
        return {}

    client = boto3.client("cloudwatch")
    period = _pick_period(start, end)

    id_map: dict[str, tuple[str, str]] = {}
    queries = []
    for i, fn in enumerate(function_names):
        dims = [{"Name": "FunctionName", "Value": fn}]
        for j, (key, metric_name, stat) in enumerate(_METRIC_SPECS):
            qid = f"m{i}_{j}"
            id_map[qid] = (fn, key)
            queries.append(
                {
                    "Id": qid,
                    "MetricStat": {
                        "Metric": {
                            "Namespace": "AWS/Lambda",
                            "MetricName": metric_name,
                            "Dimensions": dims,
                        },
                        "Period": period,
                        "Stat": stat,
                    },
                    "ReturnData": True,
                }
            )

    results: dict[str, dict[str, float]] = {fn: {} for fn in function_names}
    for chunk_start in range(0, len(queries), 500):  # GetMetricData caps at 500 queries/call
        chunk = queries[chunk_start : chunk_start + 500]
        resp = client.get_metric_data(MetricDataQueries=chunk, StartTime=start, EndTime=end)
        for series in resp["MetricDataResults"]:
            fn, key = id_map[series["Id"]]
            values = series.get("Values", [])
            if key in ("invocations", "errors", "throttles"):
                results[fn][key] = sum(values)
            else:
                results[fn][key] = (sum(values) / len(values)) if values else 0.0

    for fn in function_names:
        results[fn].setdefault("invocations", 0.0)
        results[fn].setdefault("errors", 0.0)
        results[fn].setdefault("throttles", 0.0)
        results[fn].setdefault("duration_avg_ms", 0.0)
        results[fn].setdefault("duration_p50_ms", 0.0)
        results[fn].setdefault("duration_p95_ms", 0.0)

    return results


def fetch_log_messages(
    log_group: str,
    start: datetime,
    end: datetime,
    filter_pattern: str | None = None,
    limit: int = 1000,
    timeout_s: float = 30.0,
) -> list[str]:
    """Run a CloudWatch Logs Insights query and return raw ``@message`` values.

    Returns ``[]`` (rather than raising) if the log group doesn't exist yet
    (e.g. a portal that has never received traffic) or the query times out.
    Aggregation/parsing of the JSON log lines happens in ``log_analysis.py`` so
    this stays a thin, easily-swappable AWS access layer.
    """
    client = boto3.client("logs")
    query = "fields @timestamp, @message"
    if filter_pattern:
        query += f" | filter {filter_pattern}"
    query += f" | sort @timestamp desc | limit {limit}"

    try:
        start_resp = client.start_query(
            logGroupNames=[log_group],
            startTime=int(start.timestamp()),
            endTime=int(end.timestamp()),
            queryString=query,
        )
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
            return []
        raise

    query_id = start_resp["queryId"]
    deadline = time.monotonic() + timeout_s
    resp = client.get_query_results(queryId=query_id)
    while resp["status"] in ("Running", "Scheduled") and time.monotonic() < deadline:
        time.sleep(1)
        resp = client.get_query_results(queryId=query_id)

    messages = []
    for result in resp.get("results", []):
        row = {field["field"]: field["value"] for field in result}
        if "@message" in row:
            messages.append(row["@message"])
    return messages
