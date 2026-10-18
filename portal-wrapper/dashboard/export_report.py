"""Export a CSV set + PDF usage report for the Responsive Cities MCP portals.

Reuses the same data-fetching code as app.py (portals.py / cloudwatch.py /
log_analysis.py) so the export always matches what the live dashboard shows
for the same environment/time range.

    AWS_PROFILE=rc-deploy .venv/bin/python export_report.py --env prod --days 7

Read-only — never writes to AWS. Output goes to exports/<env>-<timestamp>/.
"""

from __future__ import annotations

import argparse
import io
import pathlib
from datetime import datetime, timedelta, timezone

import matplotlib

matplotlib.use("Agg")  # headless: no display backend needed
import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from cloudwatch import fetch_log_messages, get_lambda_metrics
from log_analysis import (
    DURATION_FILTER,
    ERRORS_FILTER,
    TOOL_USAGE_FILTER,
    recent_errors,
    slowest_requests,
    tool_usage_breakdown,
)
from portals import discover_portal_functions

ROOT = pathlib.Path(__file__).resolve().parent


def build_usage_comparison(portals, start, end) -> pd.DataFrame:
    metrics = get_lambda_metrics([p.function_name for p in portals], start, end)
    rows = []
    for p in portals:
        m = metrics.get(p.function_name, {})
        invocations = m.get("invocations", 0.0)
        errors = m.get("errors", 0.0)
        rows.append(
            {
                "Portal": p.city,
                "Slug": p.slug,
                "Invocations": int(invocations),
                "Errors": int(errors),
                "Error rate": round((errors / invocations) if invocations else 0.0, 4),
                "Throttles": int(m.get("throttles", 0.0)),
                "Avg duration (ms)": round(m.get("duration_avg_ms", 0.0), 1),
                "p50 duration (ms)": round(m.get("duration_p50_ms", 0.0), 1),
                "p95 duration (ms)": round(m.get("duration_p95_ms", 0.0), 1),
            }
        )
    return pd.DataFrame(rows).sort_values("Invocations", ascending=False).reset_index(drop=True)


def build_tool_usage(portals, start, end) -> pd.DataFrame:
    rows = []
    for p in portals:
        messages = fetch_log_messages(p.log_group, start, end, filter_pattern=TOOL_USAGE_FILTER, limit=1000)
        for label, count in tool_usage_breakdown(messages).items():
            rows.append({"Portal": p.city, "Slug": p.slug, "Method": label, "Calls": count})
    if not rows:
        return pd.DataFrame(columns=["Portal", "Slug", "Method", "Calls"])
    return pd.DataFrame(rows).sort_values(["Portal", "Calls"], ascending=[True, False]).reset_index(drop=True)


def build_recent_errors(portals, start, end) -> pd.DataFrame:
    rows = []
    for p in portals:
        messages = fetch_log_messages(p.log_group, start, end, filter_pattern=ERRORS_FILTER, limit=500)
        for row in recent_errors(messages, limit=20):
            rows.append({"Portal": p.city, "Slug": p.slug, **row})
    if not rows:
        return pd.DataFrame(columns=["Portal", "Slug", "timestamp", "request_id", "method", "error_type", "duration_ms", "detail"])
    df = pd.DataFrame(rows).sort_values("timestamp", ascending=False).reset_index(drop=True)
    df["detail"] = df["detail"].apply(lambda d: str(d) if d is not None else "")
    return df


def build_slowest_requests(portals, start, end) -> pd.DataFrame:
    rows = []
    for p in portals:
        messages = fetch_log_messages(p.log_group, start, end, filter_pattern=DURATION_FILTER, limit=2000)
        for row in slowest_requests(messages, limit=10):
            rows.append({"Portal": p.city, "Slug": p.slug, **row})
    if not rows:
        return pd.DataFrame(columns=["Portal", "Slug", "timestamp", "request_id", "method", "success", "duration_ms"])
    return pd.DataFrame(rows).sort_values("duration_ms", ascending=False).reset_index(drop=True)


def _chart_png(fig) -> Image:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return Image(buf, width=7 * inch, height=3.2 * inch)


def _df_table(df: pd.DataFrame, max_rows: int | None = None, col_widths=None) -> Table:
    shown = df if max_rows is None else df.head(max_rows)
    data = [list(shown.columns)] + shown.astype(str).values.tolist()
    table = Table(data, repeatRows=1, colWidths=col_widths)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f0f0")]),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return table


def build_pdf(
    path: pathlib.Path,
    env: str,
    start: datetime,
    end: datetime,
    comparison_df: pd.DataFrame,
    tool_df: pd.DataFrame,
    errors_df: pd.DataFrame,
    slowest_df: pd.DataFrame,
) -> None:
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(
        str(path), pagesize=landscape(letter), topMargin=0.5 * inch, bottomMargin=0.5 * inch
    )
    story = []

    story.append(Paragraph("Responsive Cities MCP — Usage Report", styles["Title"]))
    story.append(
        Paragraph(
            f"Environment: {env} &nbsp;&nbsp; Window: {start:%Y-%m-%d %H:%M} – {end:%Y-%m-%d %H:%M} UTC "
            f"&nbsp;&nbsp; Generated: {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 16))

    # --- Usage comparison ---
    story.append(Paragraph("Usage comparison", styles["Heading2"]))
    if not comparison_df.empty:
        top = comparison_df.head(15)
        fig, ax = plt.subplots(figsize=(10, 4.5))
        x = range(len(top))
        ax.bar(x, top["Invocations"], label="Invocations", color="#2c3e50")
        ax.bar(x, top["Errors"], label="Errors", color="#e74c3c")
        ax.set_xticks(list(x))
        ax.set_xticklabels(top["Portal"], rotation=45, ha="right", fontsize=7)
        ax.set_ylabel("Count")
        ax.set_title("Invocations & errors per portal (top 15 by volume)")
        ax.legend()
        fig.tight_layout()
        story.append(_chart_png(fig))
        story.append(Spacer(1, 8))
        story.append(_df_table(comparison_df.drop(columns=["Slug"])))
    else:
        story.append(Paragraph("No data.", styles["Normal"]))
    story.append(PageBreak())

    # --- Tool usage ---
    story.append(Paragraph("Tool / method usage", styles["Heading2"]))
    if not tool_df.empty:
        overall = tool_df.groupby("Method")["Calls"].sum().sort_values(ascending=False).head(15)
        fig, ax = plt.subplots(figsize=(10, 4.5))
        ax.barh(overall.index[::-1], overall.values[::-1], color="#2980b9")
        ax.set_xlabel("Calls")
        ax.set_title("Top methods/tools called, across all portals")
        fig.tight_layout()
        story.append(_chart_png(fig))
        story.append(Spacer(1, 8))
        story.append(_df_table(tool_df.drop(columns=["Slug"]), max_rows=200))
    else:
        story.append(Paragraph("No tool/method calls found in this window.", styles["Normal"]))
    story.append(PageBreak())

    # --- Recent errors ---
    story.append(Paragraph("Recent errors", styles["Heading2"]))
    if not errors_df.empty:
        cols = ["Portal", "timestamp", "method", "error_type", "duration_ms"]
        story.append(_df_table(errors_df[cols], max_rows=200))
    else:
        story.append(Paragraph("No errors in this window.", styles["Normal"]))
    story.append(PageBreak())

    # --- Slowest requests ---
    story.append(Paragraph("Slowest requests", styles["Heading2"]))
    if not slowest_df.empty:
        cols = ["Portal", "timestamp", "method", "success", "duration_ms"]
        story.append(_df_table(slowest_df[cols], max_rows=200))
    else:
        story.append(Paragraph("No completed requests found in this window.", styles["Normal"]))

    doc.build(story)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", choices=["prod", "staging", "dev"], default="prod")
    parser.add_argument("--days", type=float, default=7.0, help="Time range in days (default: 7)")
    parser.add_argument("--output-dir", type=pathlib.Path, default=None)
    args = parser.parse_args()

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=args.days)

    out_dir = args.output_dir or ROOT / "exports" / f"{args.env}-{end:%Y%m%dT%H%M%SZ}"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Discovering {args.env} portals…")
    portals = discover_portal_functions(args.env)
    if not portals:
        print(f"No Lambda functions found matching rc-*-mcp-{args.env}. Nothing to export.")
        return 1
    print(f"Found {len(portals)} portals.")

    print("Fetching usage comparison (CloudWatch metrics)…")
    comparison_df = build_usage_comparison(portals, start, end)
    comparison_df.to_csv(out_dir / "usage_comparison.csv", index=False)

    print("Fetching tool/method usage (Logs Insights)…")
    tool_df = build_tool_usage(portals, start, end)
    tool_df.to_csv(out_dir / "tool_usage.csv", index=False)

    print("Fetching recent errors (Logs Insights)…")
    errors_df = build_recent_errors(portals, start, end)
    errors_df.to_csv(out_dir / "recent_errors.csv", index=False)

    print("Fetching slowest requests (Logs Insights)…")
    slowest_df = build_slowest_requests(portals, start, end)
    slowest_df.to_csv(out_dir / "slowest_requests.csv", index=False)

    pdf_path = out_dir / "usage_report.pdf"
    print("Building PDF report…")
    build_pdf(pdf_path, args.env, start, end, comparison_df, tool_df, errors_df, slowest_df)

    print(f"\nDone. Output in {out_dir}:")
    for f in sorted(out_dir.iterdir()):
        print(f"  {f.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
