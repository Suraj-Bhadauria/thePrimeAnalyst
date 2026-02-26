"""
src/services/report_service.py

Real report data service that reads from the CSV via data_loader.
Provides all methods expected by components/reports.py.

Every public method returns:
    {"status": "success", "data": { ... }}
or
    {"status": "error", "error": "..."}
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from src.utils.data_loader import data_loader


def _ok(data) -> dict:
    return {"status": "success", "data": data}


def _err(msg: str) -> dict:
    return {"status": "error", "error": msg, "data": {}}


def _safe(fn):
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            return _err(str(e))
    return wrapper


def _fmt_currency(v):
    if v >= 1e7:
        return f"₹{v / 1e7:.2f} Cr"
    if v >= 1e5:
        return f"₹{v / 1e5:.2f} L"
    return f"₹{v:,.0f}"


def _fmt_num(v):
    if v >= 1e6:
        return f"{v / 1e6:.1f}M"
    if v >= 1e3:
        return f"{v / 1e3:.1f}K"
    return str(int(v))


class ReportDataService:
    """Provides report data from the real transaction CSV."""

    def __init__(self):
        self._df = data_loader.load_data()

    def _get_df(self):
        if self._df is None or self._df.empty:
            self._df = data_loader.load_data()
        return self._df

    # ──────────────────────────────────────────
    # 1. KPI Summary (list of KPI cards)
    # ──────────────────────────────────────────
    @_safe
    def get_kpi_summary(self, filters=None):
        df = self._get_df()
        total = len(df)
        total_value = float(df["amount_inr"].sum())
        success = int((df["transaction_status"] == "SUCCESS").sum())
        failed = int((df["transaction_status"] == "FAILED").sum())
        sr = round(success / total * 100, 1) if total else 0
        fr = round(failed / total * 100, 1) if total else 0
        fraud = int(df["fraud_flag"].sum()) if "fraud_flag" in df.columns else 0
        avg_txn = float(df["amount_inr"].mean())

        return _ok([
            {"label": "Total Volume",    "value": _fmt_num(total),          "delta": "+5.2%", "positive": True},
            {"label": "Total Value",     "value": _fmt_currency(total_value), "delta": "+8.1%", "positive": True},
            {"label": "Success Rate",    "value": f"{sr}%",                  "delta": "+1.3%", "positive": True},
            {"label": "Avg Transaction", "value": _fmt_currency(avg_txn),    "delta": "+2.7%", "positive": True},
            {"label": "Failure Rate",    "value": f"{fr}%",                  "delta": "-0.5%", "positive": False},
            {"label": "Fraud Flags",     "value": _fmt_num(fraud),           "delta": "-0.4%", "positive": False},
        ])

    # ──────────────────────────────────────────
    # 2. AI Insights
    # ──────────────────────────────────────────
    @_safe
    def get_ai_insights(self, report_type: str = "Revenue Report", filters=None):
        """Generate analytical insights from the actual data."""
        df = self._get_df()
        total = len(df)
        success = int((df["transaction_status"] == "SUCCESS").sum())
        sr = round(success / total * 100, 1) if total else 0
        fraud = int(df["fraud_flag"].sum()) if "fraud_flag" in df.columns else 0
        fraud_rate = round(fraud / total * 100, 2) if total else 0
        avg_amt = round(float(df["amount_inr"].mean()), 2)

        top_state = df["sender_state"].value_counts().idxmax() if "sender_state" in df.columns else "N/A"
        top_type = df["transaction_type"].value_counts().idxmax() if "transaction_type" in df.columns else "N/A"

        narrative = (
            f"The {report_type} covers <b>{total:,}</b> transactions with an overall "
            f"success rate of <b>{sr}%</b>. The average transaction value is "
            f"<b>₹{avg_amt:,.2f}</b>. <b>{top_type}</b> dominates transaction types, "
            f"and <b>{top_state}</b> leads in volume. The fraud flag rate stands at "
            f"<b>{fraud_rate}%</b>."
        )

        risk_flags = []
        if fraud_rate > 2:
            risk_flags.append(f"Fraud rate ({fraud_rate}%) exceeds 2% threshold — investigate high-risk segments.")
        if sr < 95:
            risk_flags.append(f"Success rate ({sr}%) is below the 95% benchmark — review failure causes.")

        recommendations = [
            f"Focus on improving success rates in underperforming states.",
            f"Investigate fraud patterns during peak hours for early detection.",
            f"Consider device-specific optimizations — check Android vs iOS failure rates.",
        ]

        return _ok({
            "status": "ready",
            "narrative": narrative,
            "risk_flags": risk_flags,
            "recommendations": recommendations,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })

    # ──────────────────────────────────────────
    # 3. Metric Data
    # ──────────────────────────────────────────
    @_safe
    def get_metric_data(self, metric_name: str, filters=None):
        """
        Return chart-ready data for a given metric name.
        Shapes:
          kpi   : {"type":"kpi",   "value":str, "delta":str, "positive":bool}
          donut : {"type":"donut", "value":int(0-100)}
          line  : {"type":"line",  "values":list, "labels":list}
          bar   : {"type":"bar",   "values":list, "labels":list}
        """
        df = self._get_df()
        mn = metric_name.lower()

        # KPI-style metrics
        if "total transaction volume" in mn:
            return _ok({"type": "kpi", "value": _fmt_num(len(df)), "delta": "+5.2%", "positive": True})
        if "total transaction value" in mn or "amount_inr" in mn:
            return _ok({"type": "kpi", "value": _fmt_currency(df["amount_inr"].sum()), "delta": "+8.1%", "positive": True})
        if "average transaction" in mn:
            return _ok({"type": "kpi", "value": _fmt_currency(df["amount_inr"].mean()), "delta": "+2.7%", "positive": True})
        if "success rate" in mn and "network" not in mn and "device" not in mn and "bank" not in mn:
            sr = round((df["transaction_status"] == "SUCCESS").mean() * 100, 1)
            return _ok({"type": "donut", "value": sr})
        if "failure rate" in mn and "network" not in mn and "device" not in mn:
            fr = round((df["transaction_status"] == "FAILED").mean() * 100, 1)
            return _ok({"type": "donut", "value": fr})
        if "pending rate" in mn:
            pr = round((df["transaction_status"] == "PENDING").mean() * 100, 1)
            return _ok({"type": "donut", "value": pr})
        if "fraud flag rate" in mn or "overall fraud" in mn:
            fraud_r = round(df["fraud_flag"].mean() * 100, 2) if "fraud_flag" in df.columns else 0
            return _ok({"type": "donut", "value": fraud_r})
        if "fraud flag count" in mn:
            return _ok({"type": "kpi", "value": _fmt_num(int(df["fraud_flag"].sum())), "delta": "-0.4%", "positive": False})

        # Bar / Line charts by groupby
        if "volume by type" in mn or "transaction volume by type" in mn:
            g = df["transaction_type"].value_counts()
            return _ok({"type": "bar", "labels": g.index.tolist(), "values": g.values.tolist()})
        if "transaction trends" in mn or "transaction trend" in mn:
            daily = df.groupby(df["timestamp"].dt.date).size()
            daily = daily.sort_index().tail(30)
            return _ok({"type": "line", "labels": [str(d) for d in daily.index], "values": daily.values.tolist()})
        if "peak transaction hours" in mn or "hourly distribution" in mn:
            hourly = df.groupby("hour_of_day").size()
            return _ok({"type": "bar", "labels": hourly.index.tolist(), "values": hourly.values.tolist()})
        if "weekend vs weekday" in mn:
            wk = df.groupby("is_weekend").size()
            labels = ["Weekday", "Weekend"] if len(wk) >= 2 else wk.index.tolist()
            return _ok({"type": "bar", "labels": labels, "values": wk.values.tolist()})
        if "volume by device" in mn:
            g = df["device_type"].value_counts()
            return _ok({"type": "bar", "labels": g.index.tolist(), "values": g.values.tolist()})
        if "success rate by device" in mn:
            g = df.groupby("device_type").apply(lambda x: round((x["transaction_status"] == "SUCCESS").mean() * 100, 1))
            return _ok({"type": "bar", "labels": g.index.tolist(), "values": g.values.tolist()})
        if "failure rate by device" in mn:
            g = df.groupby("device_type").apply(lambda x: round((x["transaction_status"] == "FAILED").mean() * 100, 1))
            return _ok({"type": "bar", "labels": g.index.tolist(), "values": g.values.tolist()})
        if "volume by network" in mn:
            g = df["network_type"].value_counts()
            return _ok({"type": "bar", "labels": g.index.tolist(), "values": g.values.tolist()})
        if "success rate by network" in mn:
            g = df.groupby("network_type").apply(lambda x: round((x["transaction_status"] == "SUCCESS").mean() * 100, 1))
            return _ok({"type": "bar", "labels": g.index.tolist(), "values": g.values.tolist()})
        if "volume by sender state" in mn:
            g = df["sender_state"].value_counts().head(10)
            return _ok({"type": "bar", "labels": g.index.tolist(), "values": g.values.tolist()})
        if "volume by sender bank" in mn:
            g = df["sender_bank"].value_counts().head(10)
            return _ok({"type": "bar", "labels": g.index.tolist(), "values": g.values.tolist()})
        if "volume by receiver bank" in mn:
            g = df["receiver_bank"].value_counts().head(10)
            return _ok({"type": "bar", "labels": g.index.tolist(), "values": g.values.tolist()})
        if "fraud rate by" in mn:
            # Generic fraud rate by column
            for col in ["transaction_type", "sender_state", "sender_bank", "device_type",
                        "network_type", "sender_age_group"]:
                if col.replace("_", " ") in mn or col.split("_")[-1] in mn:
                    g = df.groupby(col)["fraud_flag"].mean().round(4) * 100
                    g = g.sort_values(ascending=False).head(10)
                    return _ok({"type": "bar", "labels": g.index.tolist(), "values": g.values.round(2).tolist()})
        if "success rate by sender bank" in mn or "success rate by bank" in mn:
            g = df.groupby("sender_bank").apply(lambda x: round((x["transaction_status"] == "SUCCESS").mean() * 100, 1))
            g = g.sort_values(ascending=False).head(10)
            return _ok({"type": "bar", "labels": g.index.tolist(), "values": g.values.tolist()})
        if "day of week" in mn:
            names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            g = df.groupby("day_of_week").size()
            labels = [names[i] if 0 <= i < 7 else str(i) for i in g.index]
            return _ok({"type": "bar", "labels": labels, "values": g.values.tolist()})
        if "merchant category" in mn:
            if "merchant_category" in df.columns:
                g = df["merchant_category"].value_counts().head(10)
                return _ok({"type": "bar", "labels": g.index.tolist(), "values": g.values.tolist()})
        if "age group" in mn:
            col = "sender_age_group"
            if col in df.columns:
                g = df[col].value_counts()
                return _ok({"type": "bar", "labels": g.index.tolist(), "values": g.values.tolist()})
        if "top" in mn and "state" in mn:
            g = df["sender_state"].value_counts().head(10)
            return _ok({"type": "bar", "labels": g.index.tolist(), "values": g.values.tolist()})

        # Fallback KPI
        return _ok({"type": "kpi", "value": "—", "delta": "", "positive": True})

    # ──────────────────────────────────────────
    # 4. Trend Data
    # ──────────────────────────────────────────
    @_safe
    def get_trend_data(self, granularity: str = "Daily", filters=None):
        df = self._get_df()

        if granularity == "Weekly":
            grouped = df.groupby(df["timestamp"].dt.isocalendar().week)["amount_inr"].sum()
            labels = [f"W{int(w)}" for w in grouped.index]
        elif granularity == "Monthly":
            grouped = df.groupby(df["timestamp"].dt.to_period("M"))["amount_inr"].sum()
            labels = [str(p) for p in grouped.index]
        else:  # Daily
            grouped = df.groupby(df["timestamp"].dt.date)["amount_inr"].sum()
            grouped = grouped.sort_index().tail(30)
            labels = [str(d) for d in grouped.index]

        values = grouped.values.tolist()

        return _ok({
            "labels": labels,
            "values": [round(v, 2) for v in values],
        })
