# MCP Portal Usage Dashboard

A local, read-only Streamlit dashboard for comparing usage and health across
the Responsive Cities MCP portals (`../terraform/`). It talks to CloudWatch
directly with your own AWS credentials — nothing is deployed, nothing is
public, and no new login/auth is involved.

## What it shows

- **Usage comparison** — invocations, errors, error rate, throttles, and
  avg/p50/p95 duration per portal (from `AWS/Lambda` CloudWatch metrics).
- **Tool / method usage** — which MCP tool or JSON-RPC method is being called
  per portal, parsed from the structured `core.mcp_server` request logs
  (`jsonrpc_method`/`jsonrpc_params.name`).
- **Recent errors** — the last failed requests per portal, with the
  sanitized JSON-RPC error body.
- **Slowest requests** — the highest-`duration_ms` requests per portal, to
  spot portals creeping toward the Lambda timeout.

## Run it

```bash
cd portal-wrapper/dashboard
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
AWS_PROFILE=rc-deploy .venv/bin/streamlit run app.py
```

(Plain `pip install -r requirements.txt` into a `python3 -m venv .venv` works
too if you don't have `uv`.)

Pick the environment (`prod`/`staging`/`dev`) and time range in the sidebar.
Portals are discovered live: for each portal in `portal_definitions.yaml`
it checks for a deployed `rc-<slug>-mcp-<env>` Lambda, so newly deployed or
torn-down portals show up (or drop out) automatically.

Metric/log query results are cached for 5 minutes (`st.cache_data`) so
tweaking the portal filter doesn't re-run CloudWatch Logs Insights queries or
hit API rate limits.

## Required AWS permissions

Read-only. `rc-deploy` already has everything the dashboard needs — a
`rc-deploy-dashboard-readonly` inline policy was added (2026-09-14, applied
with root credentials since `rc-deploy` is explicitly denied from modifying
itself) granting exactly:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Sid": "CloudWatchMetricsReadOnly", "Effect": "Allow", "Action": "cloudwatch:GetMetricData", "Resource": "*" },
    {
      "Sid": "LogsInsightsQueryRcLambda",
      "Effect": "Allow",
      "Action": ["logs:StartQuery", "logs:GetQueryResults", "logs:StopQuery"],
      "Resource": [
        "arn:aws:logs:*:564762345093:log-group:/aws/lambda/rc-*",
        "arn:aws:logs:*:564762345093:log-group:/aws/lambda/rc-*:*"
      ]
    }
  ]
}
```

Everything else (`lambda:GetFunction` on `rc-*`) was already covered by the
existing deploy policy — `portals.py` deliberately discovers portals via
per-slug `GetFunction` calls (from `portal_definitions.yaml`) rather than
`lambda:ListFunctions`, which `rc-deploy` doesn't have and which can't be
resource-scoped to `rc-*` anyway. `cloudwatch:GetMetricData` similarly can't
be resource-scoped — same caveat as `docs/aws-deployment.md` Appendix A.

If you're running this under a different, more restricted profile, it needs
the same two statements above (with your account ID).

## Notes on the Logs Insights queries

The dashboard pulls raw `@message` lines via CloudWatch Logs Insights and
parses/aggregates the JSON in Python (`log_analysis.py`) rather than relying
on Insights' own nested-field syntax. Verified end-to-end against real prod
log groups: the request-level fields actually come from the `core.mcp_server`
logger (`jsonrpc_method`, `jsonrpc_params`, `jsonrpc_error`) rather than the
HTTP-layer `request_body`/`response_body` originally assumed — see the
field-shape notes at the top of `log_analysis.py`.

## Files

- `app.py` — Streamlit UI.
- `portals.py` — discovers deployed portal Lambda functions, maps slug → city.
- `cloudwatch.py` — thin AWS access layer: `GetMetricData` + Logs Insights.
- `log_analysis.py` — pure parsing/aggregation of the JSON log lines (no AWS
  calls; unit-testable on its own).
