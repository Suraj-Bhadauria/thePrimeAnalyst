"""
Date Query Tool for PayInsight AI

This module provides precise calendar-date-level query capabilities for transaction data.
It is the ONLY tool in the system that can filter by actual calendar dates (e.g. 2024-12-30)
by performing timestamp-to-date extraction at query time — something no other tool can do.

This tool exists as a direct fix for a confirmed hallucination failure: when asked
"how many transactions occurred on 2024-12-30," the system previously returned the
entire dataset size (~250,000) instead of the actual daily count. This tool ensures
every date-based answer is a precise integer derived from real filtered data.

Author: Team primeFactors
"""

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
import pandas as pd
import numpy as np
from scipy import stats as scipy_stats
import json
import math
import calendar
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional, Tuple
from src.utils.data_loader import data_loader


# ---------------------------------------------------------------------------
# Input schema
# ---------------------------------------------------------------------------

class DateQueryInput(BaseModel):
    """Input schema for date query tool."""

    query_type: str = Field(
        description=(
            "Type of date query: single_date, date_range, month_breakdown, "
            "date_comparison, date_ranking, calendar_context, relative_date, "
            "date_distribution, weekday_vs_weekend_by_date, date_anomaly"
        )
    )
    parameters: str = Field(
        description=(
            "JSON string with date specifications and options: date, start_date, "
            "end_date, month, year, dates_list, reference_date, relative_period, "
            "date_format, metric, filters, top_n, include_hourly_breakdown, "
            "include_transaction_type_breakdown, include_benchmarks, "
            "anomaly_threshold_multiplier"
        )
    )


# ---------------------------------------------------------------------------
# Main tool class
# ---------------------------------------------------------------------------

class DateQueryTool:
    """
    Precise calendar-date query tool for transaction data.

    Handles single-date queries, date ranges, month breakdowns, date comparisons,
    date rankings, calendar context, relative date queries, date distributions,
    weekday-vs-weekend-by-date analysis, and date anomaly detection.

    The core innovation is timestamp-to-date extraction performed once at
    initialization, enabling precise filtering on actual calendar dates — a
    capability no other tool in the system provides.
    """

    DAY_NAMES: Dict[int, str] = {
        0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday",
        4: "Friday", 5: "Saturday", 6: "Sunday",
    }

    HOUR_LABELS: Dict[int, str] = {
        0: "12 AM", 1: "1 AM", 2: "2 AM", 3: "3 AM", 4: "4 AM", 5: "5 AM",
        6: "6 AM", 7: "7 AM", 8: "8 AM", 9: "9 AM", 10: "10 AM", 11: "11 AM",
        12: "12 PM", 13: "1 PM", 14: "2 PM", 15: "3 PM", 16: "4 PM", 17: "5 PM",
        18: "6 PM", 19: "7 PM", 20: "8 PM", 21: "9 PM", 22: "10 PM", 23: "11 PM",
    }

    # Date formats to try in order of likelihood
    _DATE_FORMATS: List[str] = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y%m%d",
        "%d-%m-%Y",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%m-%d-%Y",
        "%B %Y",
        "%b %Y",
        "%Y %B",
        "%Y %b",
        "%B %d %Y",
        "%B %d, %Y",
        "%d %B %Y",
        "%b %d %Y",
        "%b %d, %Y",
        "%d %b %Y",
        "%B %dst %Y",
        "%B %dnd %Y",
        "%B %drd %Y",
        "%B %dth %Y",
        "%d %B",
        "%B %d",
        "%b %d",
        "%d %b",
    ]

    def __init__(self) -> None:
        """
        Initialize DateQueryTool with data from the singleton loader.

        Performs timestamp-to-date extraction and pre-computes all benchmark
        statistics used across query types. This initialization runs once —
        individual queries only filter and aggregate on the date-enriched DataFrame.
        """
        self.df: pd.DataFrame = data_loader.load_data().copy()
        self.total_records: int = len(self.df)

        # --- Step 1: Parse timestamp and extract transaction_date ---
        # The timestamp column has already been converted to datetime by
        # DataLoader._preprocess.  We extract the date component.
        if not pd.api.types.is_datetime64_any_dtype(self.df["timestamp"]):
            self.df["timestamp"] = pd.to_datetime(self.df["timestamp"], errors="coerce")
        self.df["transaction_date"] = self.df["timestamp"].dt.date

        # --- Step 2: Cache date metadata ---
        date_counts = self.df.groupby("transaction_date").size()
        self.all_dates: List[date] = sorted(date_counts.index.tolist())
        self.date_range_start: date = self.all_dates[0] if self.all_dates else None
        self.date_range_end: date = self.all_dates[-1] if self.all_dates else None
        self.total_days_in_dataset: int = len(self.all_dates)

        # Daily transaction count stats
        daily_counts = date_counts.values.astype(float)
        self.daily_avg_transactions: float = round(float(np.mean(daily_counts)), 2)
        self.daily_std_transactions: float = round(float(np.std(daily_counts, ddof=1)) if len(daily_counts) > 1 else 0.0, 2)

        # Daily amount stats
        daily_amounts = self.df.groupby("transaction_date")["amount_inr"].sum()
        self.daily_avg_amount: float = round(float(daily_amounts.mean()), 2)

        # Daily failure rate
        def _daily_failure_rate(group: pd.DataFrame) -> float:
            n = len(group)
            if n == 0:
                return 0.0
            return group["transaction_status"].eq("FAILED").sum() / n * 100

        daily_failure = self.df.groupby("transaction_date").apply(_daily_failure_rate)
        self.daily_avg_failure_rate: float = round(float(daily_failure.mean()), 2)

        # Daily fraud rate
        def _daily_fraud_rate(group: pd.DataFrame) -> float:
            n = len(group)
            if n == 0:
                return 0.0
            return group["fraud_flag"].sum() / n * 100

        daily_fraud = self.df.groupby("transaction_date").apply(_daily_fraud_rate)
        self.daily_avg_fraud_rate: float = round(float(daily_fraud.mean()), 2)

        # Rank map by volume (1 = busiest)
        volume_ranked = date_counts.sort_values(ascending=False)
        self.date_to_rank_map: Dict[date, int] = {
            d: rank for rank, d in enumerate(volume_ranked.index, start=1)
        }

        # Day-of-week and weekend maps
        self.date_to_dayofweek_map: Dict[date, str] = {}
        self.date_to_weekend_map: Dict[date, bool] = {}
        for d in self.all_dates:
            dow = d.weekday()  # 0=Monday … 6=Sunday
            self.date_to_dayofweek_map[d] = self.DAY_NAMES[dow]
            self.date_to_weekend_map[d] = dow >= 5

        # Pre-cache daily metric series for anomaly/distribution queries
        self._daily_counts_series = date_counts
        self._daily_amounts_series = daily_amounts
        self._daily_failure_series = daily_failure
        self._daily_fraud_series = daily_fraud

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def query(self, query_type: str, parameters: str) -> str:
        """
        Main entry point for calendar-date queries.

        Args:
            query_type: The type of date query to perform.
            parameters: JSON string containing date specifications and options.

        Returns:
            JSON string with query results in standardised format.
        """
        try:
            params: Dict = json.loads(parameters) if parameters else {}
        except json.JSONDecodeError as exc:
            return self._error_response(
                query_type,
                f"Invalid JSON in parameters: {exc}",
                "Ensure parameters is a valid JSON string.",
            )

        dispatch = {
            "single_date": self._query_single_date,
            "date_range": self._query_date_range,
            "month_breakdown": self._query_month_breakdown,
            "month": self._query_month_breakdown,
            "date_comparison": self._query_date_comparison,
            "date_ranking": self._query_date_ranking,
            "calendar_context": self._query_calendar_context,
            "relative_date": self._query_relative_date,
            "date_distribution": self._query_date_distribution,
            "weekday_vs_weekend_by_date": self._query_weekday_vs_weekend_by_date,
            "date_anomaly": self._query_date_anomaly,
        }

        if query_type not in dispatch:
            return self._error_response(
                query_type,
                f"Unknown query_type: {query_type}",
                f"Valid types: {', '.join(dispatch.keys())}",
            )

        try:
            return dispatch[query_type](params)
        except Exception as exc:
            return self._error_response(
                query_type,
                f"Query failed: {exc}",
                "Check your parameters and try again.",
            )

    # ==================================================================
    # QUERY TYPE IMPLEMENTATIONS
    # ==================================================================

    # ------------------------------------------------------------------
    # single_date
    # ------------------------------------------------------------------

    def _query_single_date(self, params: Dict) -> str:
        """Retrieve all metrics for one specific calendar date."""
        date_str = params.get("date", "")
        parsed, fmt_detected, parse_note = self._parse_date_string(date_str)
        if parsed is None:
            return self._build_date_parse_error(date_str, "single_date")

        valid, not_found_resp = self._validate_date(parsed, "single_date", date_str, fmt_detected)
        if not valid:
            return not_found_resp

        filters = params.get("filters", [])
        include_hourly = params.get("include_hourly_breakdown", True)
        include_type_breakdown = params.get("include_transaction_type_breakdown", True)
        include_benchmarks = params.get("include_benchmarks", True)

        df_day = self._filter_to_date(parsed, filters)
        metrics = self._compute_date_metrics(df_day, parsed, include_benchmarks, include_type_breakdown)

        # Hourly breakdown
        hourly = self._compute_hourly_breakdown(df_day) if include_hourly else None

        # Peak / slowest hour
        peak_hour, slowest_hour = self._compute_peak_slowest_hour(df_day)

        # Date context statement
        total_txn = metrics["total_transactions"]
        dow_label = self.date_to_dayofweek_map.get(parsed, "")
        vs_avg_pct = metrics.get("vs_daily_avg_pct", 0.0)
        above_below = "above" if vs_avg_pct > 0 else ("below" if vs_avg_pct < 0 else "at")
        context_stmt = (
            f"{parsed.isoformat()} was a {dow_label}, with {total_txn:,} transactions — "
            f"{abs(vs_avg_pct):.1f}% {above_below} the dataset daily average of "
            f"{self.daily_avg_transactions:,.0f}"
        )

        headline = self._generate_headline_answer(
            "single_date", total_txn=total_txn, date_val=parsed, dow=dow_label
        )

        above_or_below = self._above_or_below(vs_avg_pct)

        return self._wrap_response(
            success=True,
            query_type="single_date",
            date_scope=f"Single date: {parsed.isoformat()} ({dow_label})",
            filters_applied=filters,
            date_not_in_dataset=False,
            primary_result=metrics,
            hourly_breakdown=hourly,
            include_benchmarks=include_benchmarks,
            mode_specific_output={
                "peak_hour_on_date": peak_hour,
                "slowest_hour_on_date": slowest_hour,
                "date_context_statement": context_stmt,
            },
            headline_answer=headline,
            key_finding=f"{parsed.isoformat()} recorded {total_txn:,} transactions with a {metrics['failure_rate_pct']:.2f}% failure rate.",
            date_context_statement=context_stmt,
            above_or_below=above_or_below,
            executive_narrative=(
                f"On {parsed.isoformat()} ({dow_label}), the platform processed {total_txn:,} transactions "
                f"totaling ₹{metrics['total_amount_inr']:,.2f}. "
                f"This was {abs(vs_avg_pct):.1f}% {above_below} the daily average. "
                f"The failure rate was {metrics['failure_rate_pct']:.2f}% and the fraud flag rate was {metrics['fraud_rate_pct']:.2f}%."
            ),
            date_parsed_as=f"{parsed.isoformat()} (parsed from '{date_str}')",
            fmt_detected=fmt_detected,
            parse_note=parse_note,
        )

    # ------------------------------------------------------------------
    # date_range
    # ------------------------------------------------------------------

    def _query_date_range(self, params: Dict) -> str:
        """Retrieve aggregated and day-by-day metrics across a range of dates."""
        start_str = params.get("start_date", "")
        end_str = params.get("end_date", "")
        start_parsed, s_fmt, s_note = self._parse_date_string(start_str)
        end_parsed, e_fmt, e_note = self._parse_date_string(end_str)
        if start_parsed is None:
            return self._build_date_parse_error(start_str, "date_range")
        if end_parsed is None:
            return self._build_date_parse_error(end_str, "date_range")

        # Swap if inverted
        swap_note = ""
        if start_parsed > end_parsed:
            start_parsed, end_parsed = end_parsed, start_parsed
            swap_note = "start_date was after end_date — they were swapped automatically."

        filters = params.get("filters", [])
        include_hourly = params.get("include_hourly_breakdown", False)
        include_type_breakdown = params.get("include_transaction_type_breakdown", True)
        include_benchmarks = params.get("include_benchmarks", True)
        metric = params.get("metric", "volume")

        df_range = self._filter_to_date_range(start_parsed, end_parsed, filters)
        dates_in_range = [d for d in self.all_dates if start_parsed <= d <= end_parsed]
        all_calendar_dates = self._calendar_dates_between(start_parsed, end_parsed)
        days_without = [d.isoformat() for d in all_calendar_dates if d not in set(dates_in_range)]

        # Range-level aggregates
        total_txn = len(df_range)
        total_amount = round(float(df_range["amount_inr"].sum()), 2)
        success_ct = int(df_range["transaction_status"].eq("SUCCESS").sum())
        failed_ct = int(df_range["transaction_status"].eq("FAILED").sum())
        pending_ct = int(df_range["transaction_status"].eq("PENDING").sum())
        fraud_ct = int(df_range["fraud_flag"].sum())

        overall_failure = round(failed_ct / total_txn * 100, 2) if total_txn else 0.0
        overall_fraud = round(fraud_ct / total_txn * 100, 2) if total_txn else 0.0
        overall_success = round(success_ct / total_txn * 100, 2) if total_txn else 0.0

        # Day-by-day
        day_by_day = []
        daily_counts_list: List[int] = []
        for d in all_calendar_dates:
            df_d = df_range[df_range["transaction_date"] == d] if d in set(dates_in_range) else pd.DataFrame()
            m = self._compute_date_metrics(df_d, d, include_benchmarks, include_type_breakdown)
            if include_hourly:
                m["hourly_breakdown"] = self._compute_hourly_breakdown(df_d) if len(df_d) > 0 else []
            day_by_day.append(m)
            daily_counts_list.append(m["total_transactions"])

        # Busiest / quietest
        non_zero = [(d, c) for d, c in zip(all_calendar_dates, daily_counts_list) if c > 0]
        busiest = max(non_zero, key=lambda x: x[1]) if non_zero else (None, 0)
        quietest = min(non_zero, key=lambda x: x[1]) if non_zero else (None, 0)

        # Trend: first half vs second half avg
        mid = len(daily_counts_list) // 2
        first_half = daily_counts_list[:mid] if mid > 0 else daily_counts_list
        second_half = daily_counts_list[mid:] if mid > 0 else daily_counts_list
        fh_avg = np.mean(first_half) if first_half else 0
        sh_avg = np.mean(second_half) if second_half else 0
        if sh_avg > fh_avg * 1.05:
            range_trend = "Rising"
        elif sh_avg < fh_avg * 0.95:
            range_trend = "Falling"
        else:
            range_trend = "Stable"

        headline = self._generate_headline_answer(
            "date_range",
            total_txn=total_txn,
            start=start_parsed, end=end_parsed,
            n_days=len(all_calendar_dates),
        )

        exec_note = swap_note or ""

        return self._wrap_response(
            success=True,
            query_type="date_range",
            date_scope=f"Date range: {start_parsed.isoformat()} to {end_parsed.isoformat()}",
            filters_applied=filters,
            date_not_in_dataset=False,
            primary_result={
                "total_transactions": total_txn,
                "total_transactions_formatted": f"{total_txn:,}",
                "total_amount_inr": total_amount,
                "overall_success_rate_pct": overall_success,
                "overall_failure_rate_pct": overall_failure,
                "overall_fraud_rate_pct": overall_fraud,
                "days_in_range": len(all_calendar_dates),
                "days_with_data": len(dates_in_range),
                "days_without_data": days_without,
            },
            hourly_breakdown=None,
            include_benchmarks=include_benchmarks,
            mode_specific_output={
                "day_by_day": day_by_day,
                "busiest_date": {"date": busiest[0].isoformat() if busiest[0] else None, "count": busiest[1]},
                "quietest_date": {"date": quietest[0].isoformat() if quietest[0] else None, "count": quietest[1]},
                "range_trend": range_trend,
            },
            headline_answer=headline,
            key_finding=(
                f"Across {len(all_calendar_dates)} days, {total_txn:,} transactions were processed "
                f"with a {overall_failure:.2f}% failure rate. Volume trend: {range_trend}."
            ),
            date_context_statement=(
                f"Date range {start_parsed.isoformat()} to {end_parsed.isoformat()} contained "
                f"{len(dates_in_range)} days with data out of {len(all_calendar_dates)} calendar days."
            ),
            above_or_below="N/A",
            executive_narrative=(
                f"Between {start_parsed.isoformat()} and {end_parsed.isoformat()}, the platform processed "
                f"{total_txn:,} transactions totaling ₹{total_amount:,.2f}. "
                f"The busiest day was {busiest[0].isoformat() if busiest[0] else 'N/A'} with {busiest[1]:,} transactions. "
                f"Volume trend across the period: {range_trend}."
            ),
            date_parsed_as=f"{start_parsed.isoformat()} to {end_parsed.isoformat()}",
            fmt_detected=s_fmt,
            parse_note=exec_note,
        )

    # ------------------------------------------------------------------
    # month_breakdown
    # ------------------------------------------------------------------

    def _query_month_breakdown(self, params: Dict) -> str:
        """Full day-by-day breakdown for an entire month."""
        month = params.get("month")
        year = params.get("year")

        # If month/year not provided, try parsing from a date string
        if month is None or year is None:
            date_str = params.get("date", params.get("start_date", ""))
            if date_str:
                parsed, _, _ = self._parse_date_string(str(date_str))
                if parsed:
                    month = parsed.month
                    year = parsed.year

        # Last-resort: try extracting month name + year from original_question
        if month is None or year is None:
            import re as _re
            orig_q = params.get("original_question", "")
            for src in [params.get("date", ""), orig_q]:
                if not src:
                    continue
                src_lower = str(src).strip().lower()
                _month_names = {name.lower(): i for i, name in enumerate(calendar.month_name) if i}
                _month_abbrs = {name.lower(): i for i, name in enumerate(calendar.month_abbr) if i}
                all_months = {**_month_names, **_month_abbrs}
                for mname, mnum in all_months.items():
                    if mname in src_lower:
                        ym = _re.search(r'\b(20\d{2})\b', src_lower)
                        if ym:
                            month = mnum
                            year = int(ym.group(1))
                            break
                if month is not None and year is not None:
                    break

        if month is None or year is None:
            return self._error_response("month_breakdown", "month and year are required.", "Provide month (1-12) and year.")

        month = int(month)
        year = int(year)
        _, last_day = calendar.monthrange(year, month)
        start = date(year, month, 1)
        end = date(year, month, last_day)
        month_label = f"{calendar.month_name[month]} {year}"

        filters = params.get("filters", [])
        include_type_breakdown = params.get("include_transaction_type_breakdown", True)
        include_benchmarks = params.get("include_benchmarks", True)

        all_calendar = self._calendar_dates_between(start, end)
        dates_with_data = [d for d in self.all_dates if start <= d <= end]

        df_month = self._filter_to_date_range(start, end, filters)
        total_txn = len(df_month)
        total_amount = round(float(df_month["amount_inr"].sum()), 2)

        # Day-by-day
        day_by_day = []
        daily_counts: List[int] = []
        weekday_counts: List[int] = []
        weekend_counts: List[int] = []
        best_day = (None, 0)
        worst_day = (None, float("inf"))

        for d in all_calendar:
            df_d = df_month[df_month["transaction_date"] == d] if d in set(dates_with_data) else pd.DataFrame()
            m = self._compute_date_metrics(df_d, d, include_benchmarks, include_type_breakdown)
            day_by_day.append(m)
            c = m["total_transactions"]
            daily_counts.append(c)

            if d.weekday() < 5:
                weekday_counts.append(c)
            else:
                weekend_counts.append(c)

            if c > best_day[1]:
                best_day = (d, c)
            if 0 < c < worst_day[1]:
                worst_day = (d, c)

        if worst_day[0] is None:
            worst_day = (None, 0)

        weekday_avg = round(float(np.mean(weekday_counts)), 2) if weekday_counts else 0.0
        weekend_avg = round(float(np.mean(weekend_counts)), 2) if weekend_counts else 0.0
        month_daily_avg = round(float(np.mean(daily_counts)), 2) if daily_counts else 0.0
        vs_dataset = round(month_daily_avg - self.daily_avg_transactions, 2)
        vs_dataset_pct = round(vs_dataset / self.daily_avg_transactions * 100, 2) if self.daily_avg_transactions else 0.0

        headline = self._generate_headline_answer(
            "month_breakdown",
            total_txn=total_txn, month_label=month_label,
            daily_avg=month_daily_avg,
        )

        return self._wrap_response(
            success=True,
            query_type="month_breakdown",
            date_scope=f"Month: {month_label}",
            filters_applied=filters,
            date_not_in_dataset=False,
            primary_result={
                "month_label": month_label,
                "total_transactions": total_txn,
                "total_transactions_formatted": f"{total_txn:,}",
                "total_amount_inr": total_amount,
                "days_in_month": len(all_calendar),
                "days_with_data": len(dates_with_data),
            },
            hourly_breakdown=None,
            include_benchmarks=include_benchmarks,
            mode_specific_output={
                "day_by_day": day_by_day,
                "month_totals": {
                    "total_transactions": total_txn,
                    "total_amount_inr": total_amount,
                    "daily_avg_transactions": month_daily_avg,
                },
                "weekday_avg_daily": weekday_avg,
                "weekend_avg_daily": weekend_avg,
                "best_day_of_month": {"date": best_day[0].isoformat() if best_day[0] else None, "count": best_day[1]},
                "worst_day_of_month": {"date": worst_day[0].isoformat() if worst_day[0] else None, "count": worst_day[1]},
                "month_vs_dataset_avg": {
                    "month_daily_avg": month_daily_avg,
                    "dataset_daily_avg": self.daily_avg_transactions,
                    "difference": vs_dataset,
                    "difference_pct": vs_dataset_pct,
                },
            },
            headline_answer=headline,
            key_finding=(
                f"{month_label} processed {total_txn:,} transactions across {len(dates_with_data)} days, "
                f"averaging {month_daily_avg:,.0f} per day."
            ),
            date_context_statement=(
                f"{month_label} daily average was {abs(vs_dataset_pct):.1f}% "
                f"{'above' if vs_dataset_pct > 0 else 'below'} the dataset-wide daily average."
            ),
            above_or_below=self._above_or_below(vs_dataset_pct),
            executive_narrative=(
                f"In {month_label}, the platform recorded {total_txn:,} transactions (₹{total_amount:,.2f}). "
                f"Weekday average was {weekday_avg:,.0f}/day vs weekend average of {weekend_avg:,.0f}/day. "
                f"The busiest day was {best_day[0].isoformat() if best_day[0] else 'N/A'} with {best_day[1]:,} transactions."
            ),
            date_parsed_as=f"{month_label}",
            fmt_detected="month/year",
            parse_note="",
        )

    # ------------------------------------------------------------------
    # date_comparison
    # ------------------------------------------------------------------

    def _query_date_comparison(self, params: Dict) -> str:
        """Compare metrics between two or more specific dates side by side."""
        dates_list_raw = params.get("dates_list", [])
        if len(dates_list_raw) < 2:
            return self._error_response("date_comparison", "dates_list must contain at least 2 dates.", "Provide 2-7 date strings.")

        filters = params.get("filters", [])
        metric = params.get("metric", "volume")
        include_type_breakdown = params.get("include_transaction_type_breakdown", True)
        include_benchmarks = params.get("include_benchmarks", True)

        parsed_dates: List[Tuple[date, str, str]] = []
        for ds in dates_list_raw[:7]:
            p, fmt, note = self._parse_date_string(ds)
            if p is None:
                return self._build_date_parse_error(ds, "date_comparison")
            parsed_dates.append((p, fmt, ds))

        # Compute metrics per date
        date_metrics: List[Dict] = []
        for p, _, _ in parsed_dates:
            if p not in set(self.all_dates):
                m = self._empty_date_metrics(p)
            else:
                df_d = self._filter_to_date(p, filters)
                m = self._compute_date_metrics(df_d, p, include_benchmarks, include_type_breakdown)
            date_metrics.append(m)

        # Comparison table transposition
        comparison_table: Dict[str, Dict[str, Any]] = {}
        metric_keys = [
            "total_transactions", "success_rate_pct", "failure_rate_pct",
            "fraud_rate_pct", "total_amount_inr", "avg_amount_inr",
        ]
        winner_per_metric: Dict[str, str] = {}
        for mk in metric_keys:
            row: Dict[str, Any] = {}
            best_val = None
            best_date = None
            for i, (p, _, _) in enumerate(parsed_dates):
                val = date_metrics[i].get(mk, 0)
                row[p.isoformat()] = val
                # For failure/fraud lower is better
                if mk in ("failure_rate_pct", "fraud_rate_pct"):
                    if best_val is None or val < best_val:
                        best_val = val
                        best_date = p.isoformat()
                else:
                    if best_val is None or val > best_val:
                        best_val = val
                        best_date = p.isoformat()
            comparison_table[mk] = row
            winner_per_metric[mk] = best_date

        counts = [(p.isoformat(), date_metrics[i]["total_transactions"]) for i, (p, _, _) in enumerate(parsed_dates)]
        overall_busiest = max(counts, key=lambda x: x[1])
        overall_quietest = min(counts, key=lambda x: x[1])

        day_labels = {p.isoformat(): self.date_to_dayofweek_map.get(p, "") for p, _, _ in parsed_dates}

        # Head-to-head summary for 2 dates
        head_to_head = None
        if len(parsed_dates) == 2:
            d1, d2 = parsed_dates[0][0], parsed_dates[1][0]
            c1, c2 = date_metrics[0]["total_transactions"], date_metrics[1]["total_transactions"]
            diff = c1 - c2
            pct_diff = round(abs(diff) / max(c2, 1) * 100, 1)
            higher = d1.isoformat() if diff > 0 else d2.isoformat()
            head_to_head = (
                f"{d1.isoformat()} had {c1:,} transactions vs {d2.isoformat()} with {c2:,} — "
                f"a difference of {abs(diff):,} ({pct_diff}% higher on {higher})."
            )

        # vs each other
        vs_each = {}
        for i, (pi, _, _) in enumerate(parsed_dates):
            for j, (pj, _, _) in enumerate(parsed_dates):
                if i >= j:
                    continue
                ci = date_metrics[i]["total_transactions"]
                cj = date_metrics[j]["total_transactions"]
                diff = ci - cj
                pct = round(abs(diff) / max(cj, 1) * 100, 1) if cj else 0.0
                vs_each[f"{pi.isoformat()} vs {pj.isoformat()}"] = {
                    "absolute_difference": diff,
                    "percentage_difference": pct,
                    "higher": pi.isoformat() if diff > 0 else pj.isoformat(),
                }

        headline = self._generate_headline_answer(
            "date_comparison",
            dates_info=[(p.isoformat(), date_metrics[i]["total_transactions"]) for i, (p, _, _) in enumerate(parsed_dates)],
        )

        return self._wrap_response(
            success=True,
            query_type="date_comparison",
            date_scope=f"Comparing {len(parsed_dates)} dates: {', '.join(p.isoformat() for p, _, _ in parsed_dates)}",
            filters_applied=filters,
            date_not_in_dataset=False,
            primary_result={
                "date_metrics": {p.isoformat(): date_metrics[i] for i, (p, _, _) in enumerate(parsed_dates)},
                "comparison_table": comparison_table,
            },
            hourly_breakdown=None,
            include_benchmarks=include_benchmarks,
            mode_specific_output={
                "winner_per_metric": winner_per_metric,
                "overall_busiest_date": {"date": overall_busiest[0], "count": overall_busiest[1]},
                "overall_quietest_date": {"date": overall_quietest[0], "count": overall_quietest[1]},
                "day_of_week_labels": day_labels,
                "vs_each_other": vs_each,
                "head_to_head_summary": head_to_head,
            },
            headline_answer=headline,
            key_finding=head_to_head or f"Busiest compared date: {overall_busiest[0]} ({overall_busiest[1]:,} txns).",
            date_context_statement=f"Compared {len(parsed_dates)} dates side-by-side.",
            above_or_below="N/A",
            executive_narrative=(
                f"Compared {len(parsed_dates)} dates. The busiest was {overall_busiest[0]} with "
                f"{overall_busiest[1]:,} transactions, while the quietest was {overall_quietest[0]} "
                f"with {overall_quietest[1]:,}."
            ),
            date_parsed_as=", ".join(f"{p.isoformat()} (from '{raw}')" for p, _, raw in parsed_dates),
            fmt_detected="multiple",
            parse_note="",
        )

    # ------------------------------------------------------------------
    # date_ranking
    # ------------------------------------------------------------------

    def _query_date_ranking(self, params: Dict) -> str:
        """Rank all dates in the dataset by a chosen metric."""
        metric = params.get("metric", "volume")
        top_n = int(params.get("top_n", 10))
        filters = params.get("filters", [])
        include_benchmarks = params.get("include_benchmarks", True)

        # Compute metric per date
        metric_per_date = self._compute_metric_per_date(metric, filters)
        sorted_desc = sorted(metric_per_date.items(), key=lambda x: x[1], reverse=True)
        sorted_asc = sorted(metric_per_date.items(), key=lambda x: x[1])

        top_dates = sorted_desc[:top_n]
        bottom_dates = sorted_asc[:top_n]

        # Build ranked entries
        def _build_entry(rank: int, d: date, val: float) -> Dict:
            return {
                "rank": rank,
                "date": d.isoformat(),
                "day_of_week_label": self.date_to_dayofweek_map.get(d, ""),
                "is_weekend": self.date_to_weekend_map.get(d, False),
                "metric_value": round(val, 2),
                "vs_daily_avg": round(val - self.daily_avg_transactions, 2) if metric == "volume" else None,
                "vs_daily_avg_pct": round((val - self.daily_avg_transactions) / self.daily_avg_transactions * 100, 2) if metric == "volume" and self.daily_avg_transactions else None,
            }

        top_entries = [_build_entry(i + 1, d, v) for i, (d, v) in enumerate(top_dates)]
        bottom_entries = [_build_entry(len(sorted_desc) - i, d, v) for i, (d, v) in enumerate(bottom_dates)]

        # Weekday/weekend top
        weekday_top = next(((d, v) for d, v in sorted_desc if not self.date_to_weekend_map.get(d, False)), (None, 0))
        weekend_top = next(((d, v) for d, v in sorted_desc if self.date_to_weekend_map.get(d, False)), (None, 0))

        # Distribution summary
        vals = [v for _, v in metric_per_date.items()]
        dist_summary = {
            "min": round(min(vals), 2) if vals else 0,
            "max": round(max(vals), 2) if vals else 0,
            "mean": round(float(np.mean(vals)), 2) if vals else 0,
            "median": round(float(np.median(vals)), 2) if vals else 0,
            "std": round(float(np.std(vals, ddof=1)), 2) if len(vals) > 1 else 0,
        }

        headline = self._generate_headline_answer(
            "date_ranking",
            top_date=top_dates[0] if top_dates else None,
            bottom_date=bottom_dates[0] if bottom_dates else None,
            metric=metric,
        )

        return self._wrap_response(
            success=True,
            query_type="date_ranking",
            date_scope=f"All {self.total_days_in_dataset} dates ranked by {metric}",
            filters_applied=filters,
            date_not_in_dataset=False,
            primary_result={
                "metric": metric,
                "top_n_dates": top_entries,
                "bottom_n_dates": bottom_entries,
            },
            hourly_breakdown=None,
            include_benchmarks=include_benchmarks,
            mode_specific_output={
                "weekday_top_date": {"date": weekday_top[0].isoformat() if weekday_top[0] else None, "value": round(weekday_top[1], 2)},
                "weekend_top_date": {"date": weekend_top[0].isoformat() if weekend_top[0] else None, "value": round(weekend_top[1], 2)},
                "metric_distribution_summary": dist_summary,
            },
            headline_answer=headline,
            key_finding=(
                f"Top date by {metric}: {top_dates[0][0].isoformat() if top_dates else 'N/A'} "
                f"({round(top_dates[0][1], 2) if top_dates else 0}). "
                f"Bottom: {bottom_dates[0][0].isoformat() if bottom_dates else 'N/A'} ({round(bottom_dates[0][1], 2) if bottom_dates else 0})."
            ),
            date_context_statement=f"Ranked {len(metric_per_date)} dates by {metric}.",
            above_or_below="N/A",
            executive_narrative=(
                f"Among {len(metric_per_date)} dates, {top_dates[0][0].isoformat() if top_dates else 'N/A'} "
                f"led with a {metric} of {round(top_dates[0][1], 2) if top_dates else 0}, while "
                f"{bottom_dates[0][0].isoformat() if bottom_dates else 'N/A'} was the lowest "
                f"at {round(bottom_dates[0][1], 2) if bottom_dates else 0}."
            ),
            date_parsed_as="all dates",
            fmt_detected="N/A",
            parse_note="",
        )

    # ------------------------------------------------------------------
    # calendar_context
    # ------------------------------------------------------------------

    def _query_calendar_context(self, params: Dict) -> str:
        """Enrich a specific date with full calendar context and peer comparisons."""
        date_str = params.get("date", "")
        parsed, fmt_detected, parse_note = self._parse_date_string(date_str)
        if parsed is None:
            return self._build_date_parse_error(date_str, "calendar_context")

        valid, resp = self._validate_date(parsed, "calendar_context", date_str, fmt_detected)
        if not valid:
            return resp

        filters = params.get("filters", [])
        include_benchmarks = params.get("include_benchmarks", True)
        include_type_breakdown = params.get("include_transaction_type_breakdown", True)

        df_day = self._filter_to_date(parsed, filters)
        metrics = self._compute_date_metrics(df_day, parsed, include_benchmarks, include_type_breakdown)

        # Same weekday comparison
        dow = parsed.weekday()
        same_weekday_dates = [d for d in self.all_dates if d.weekday() == dow and d != parsed]
        same_weekday_counts = [int(self._daily_counts_series.get(d, 0)) for d in same_weekday_dates]
        same_weekday_avg = round(float(np.mean(same_weekday_counts)), 2) if same_weekday_counts else 0.0
        this_count = metrics["total_transactions"]
        vs_same_wd = round(this_count - same_weekday_avg, 2)
        vs_same_wd_pct = round(vs_same_wd / same_weekday_avg * 100, 2) if same_weekday_avg else 0.0

        # Adjacent dates
        prev_date = parsed - timedelta(days=1)
        next_date = parsed + timedelta(days=1)
        adjacent = {}
        for label, adj_d in [("previous_day", prev_date), ("next_day", next_date)]:
            if adj_d in set(self.all_dates):
                df_adj = self._filter_to_date(adj_d, filters)
                adjacent[label] = self._compute_date_metrics(df_adj, adj_d, False, False)
            else:
                adjacent[label] = None

        # Week context
        week_start = parsed - timedelta(days=parsed.weekday())  # Monday
        week_end = week_start + timedelta(days=6)
        week_dates = [d for d in self.all_dates if week_start <= d <= week_end]
        week_counts = [int(self._daily_counts_series.get(d, 0)) for d in week_dates]
        week_total = sum(week_counts)
        week_avg = round(float(np.mean(week_counts)), 2) if week_counts else 0.0

        # Month context
        month_start = date(parsed.year, parsed.month, 1)
        _, last_day_num = calendar.monthrange(parsed.year, parsed.month)
        month_end = date(parsed.year, parsed.month, last_day_num)
        month_dates = [d for d in self.all_dates if month_start <= d <= month_end]
        month_counts = [int(self._daily_counts_series.get(d, 0)) for d in month_dates]
        month_avg = round(float(np.mean(month_counts)), 2) if month_counts else 0.0
        week_of_month = (parsed.day - 1) // 7 + 1

        is_first = parsed.day == 1
        is_last = parsed.day == last_day_num
        quarter = f"Q{(parsed.month - 1) // 3 + 1}"

        # Calendar note
        cal_notes = []
        if is_first:
            cal_notes.append("This is the first day of the month.")
        if is_last:
            cal_notes.append("This is the last day of the month.")
        if parsed.month == 12 and parsed.day >= 25:
            cal_notes.append("This date falls in the last week of the year.")
        if parsed.month == 12 and parsed.day == 24:
            cal_notes.append("This is Christmas Eve.")
        if parsed.month == 12 and parsed.day == 25:
            cal_notes.append("This is Christmas Day.")
        if parsed.month == 1 and parsed.day == 1:
            cal_notes.append("This is New Year's Day.")
        if parsed.weekday() == 0 and parsed.day <= 7:
            cal_notes.append("This is the first Monday of the month.")
        calendar_note = " ".join(cal_notes) if cal_notes else ""

        dow_label = self.date_to_dayofweek_map.get(parsed, "")
        headline = self._generate_headline_answer(
            "single_date", total_txn=this_count, date_val=parsed, dow=dow_label
        )

        return self._wrap_response(
            success=True,
            query_type="calendar_context",
            date_scope=f"Calendar context for {parsed.isoformat()} ({dow_label})",
            filters_applied=filters,
            date_not_in_dataset=False,
            primary_result=metrics,
            hourly_breakdown=None,
            include_benchmarks=include_benchmarks,
            mode_specific_output={
                "same_weekday_dates": [d.isoformat() for d in same_weekday_dates],
                "same_weekday_avg": same_weekday_avg,
                "vs_same_weekday_avg": {"absolute": vs_same_wd, "percentage": vs_same_wd_pct},
                "adjacent_dates": {k: v for k, v in adjacent.items()},
                "week_context": {
                    "week_start": week_start.isoformat(),
                    "week_end": week_end.isoformat(),
                    "week_total_transactions": week_total,
                    "week_daily_avg": week_avg,
                    "dates_in_week": [d.isoformat() for d in week_dates],
                },
                "month_context": {
                    "month_label": f"{calendar.month_name[parsed.month]} {parsed.year}",
                    "week_of_month": week_of_month,
                    "month_daily_avg": month_avg,
                    "vs_month_avg": round(this_count - month_avg, 2),
                    "vs_month_avg_pct": round((this_count - month_avg) / month_avg * 100, 2) if month_avg else 0.0,
                },
                "is_first_of_month": is_first,
                "is_last_of_month": is_last,
                "quarter": quarter,
                "calendar_note": calendar_note,
            },
            headline_answer=headline,
            key_finding=(
                f"{parsed.isoformat()} ({dow_label}) had {this_count:,} transactions — "
                f"{abs(vs_same_wd_pct):.1f}% {'above' if vs_same_wd_pct > 0 else 'below'} the average for other {dow_label}s."
            ),
            date_context_statement=(
                f"{parsed.isoformat()} is a {dow_label} in week {week_of_month} of "
                f"{calendar.month_name[parsed.month]} {parsed.year} ({quarter})."
            ),
            above_or_below=self._above_or_below(vs_same_wd_pct),
            executive_narrative=(
                f"{parsed.isoformat()} was a {dow_label} with {this_count:,} transactions. "
                f"Compared to other {dow_label}s (avg {same_weekday_avg:,.0f}), it was "
                f"{abs(vs_same_wd_pct):.1f}% {'higher' if vs_same_wd_pct > 0 else 'lower'}. "
                f"The week's total was {week_total:,} and the month average was {month_avg:,.0f}/day."
            ),
            date_parsed_as=f"{parsed.isoformat()} (parsed from '{date_str}')",
            fmt_detected=fmt_detected,
            parse_note=parse_note,
        )

    # ------------------------------------------------------------------
    # relative_date
    # ------------------------------------------------------------------

    def _query_relative_date(self, params: Dict) -> str:
        """Query using relative time references."""
        ref_str = params.get("reference_date", params.get("date", ""))
        period = params.get("relative_period", "last_7_days")
        parsed, fmt_detected, parse_note = self._parse_date_string(ref_str)
        if parsed is None:
            return self._build_date_parse_error(ref_str, "relative_date")

        filters = params.get("filters", [])
        include_benchmarks = params.get("include_benchmarks", True)

        # Get reference date metrics
        ref_in_dataset = parsed in set(self.all_dates)
        if ref_in_dataset:
            df_ref = self._filter_to_date(parsed, filters)
            ref_metrics = self._compute_date_metrics(df_ref, parsed, include_benchmarks, False)
        else:
            ref_metrics = self._empty_date_metrics(parsed)

        # Compute comparative period
        comp_label = period
        comp_metrics: Dict[str, Any] = {}
        comp_dates: List[date] = []

        if period == "last_7_days":
            comp_start = parsed - timedelta(days=7)
            comp_end = parsed - timedelta(days=1)
            comp_dates = [d for d in self.all_dates if comp_start <= d <= comp_end]
            comp_label = f"7 days before {parsed.isoformat()}"
        elif period == "last_30_days":
            comp_start = parsed - timedelta(days=30)
            comp_end = parsed - timedelta(days=1)
            comp_dates = [d for d in self.all_dates if comp_start <= d <= comp_end]
            comp_label = f"30 days before {parsed.isoformat()}"
        elif period == "same_day_last_week":
            target = parsed - timedelta(days=7)
            comp_dates = [target] if target in set(self.all_dates) else []
            comp_label = f"Same day last week ({target.isoformat()})"
        elif period == "weekly_average":
            week_start = parsed - timedelta(days=parsed.weekday())
            week_end = week_start + timedelta(days=6)
            comp_dates = [d for d in self.all_dates if week_start <= d <= week_end]
            comp_label = f"Week of {week_start.isoformat()} to {week_end.isoformat()}"
        elif period == "monthly_average":
            month_start = date(parsed.year, parsed.month, 1)
            _, ld = calendar.monthrange(parsed.year, parsed.month)
            month_end = date(parsed.year, parsed.month, ld)
            comp_dates = [d for d in self.all_dates if month_start <= d <= month_end]
            comp_label = f"{calendar.month_name[parsed.month]} {parsed.year}"
        elif period == "previous_day":
            prev = parsed - timedelta(days=1)
            comp_dates = [prev] if prev in set(self.all_dates) else []
            comp_label = f"Previous day ({prev.isoformat()})"
        elif period == "next_day":
            nxt = parsed + timedelta(days=1)
            comp_dates = [nxt] if nxt in set(self.all_dates) else []
            comp_label = f"Next day ({nxt.isoformat()})"
        else:
            return self._error_response("relative_date", f"Unknown relative_period: {period}",
                                        "Valid: last_7_days, last_30_days, same_day_last_week, weekly_average, monthly_average, previous_day, next_day")

        # Compute comp metrics as daily average
        if comp_dates:
            comp_counts = [int(self._daily_counts_series.get(d, 0)) for d in comp_dates]
            comp_avg_txn = round(float(np.mean(comp_counts)), 2)
            comp_total = sum(comp_counts)
        else:
            comp_avg_txn = 0.0
            comp_total = 0

        ref_count = ref_metrics["total_transactions"]
        abs_diff = round(ref_count - comp_avg_txn, 2)
        pct_diff = round(abs_diff / comp_avg_txn * 100, 2) if comp_avg_txn else 0.0

        if pct_diff > 5:
            trend_dir = "Above Average"
        elif pct_diff < -5:
            trend_dir = "Below Average"
        else:
            trend_dir = "At Average"

        headline = self._generate_headline_answer(
            "single_date", total_txn=ref_count, date_val=parsed,
            dow=self.date_to_dayofweek_map.get(parsed, ""),
        )

        return self._wrap_response(
            success=True,
            query_type="relative_date",
            date_scope=f"{parsed.isoformat()} vs {comp_label}",
            filters_applied=filters,
            date_not_in_dataset=not ref_in_dataset,
            primary_result=ref_metrics,
            hourly_breakdown=None,
            include_benchmarks=include_benchmarks,
            mode_specific_output={
                "relative_period": period,
                "comparative_label": comp_label,
                "comparative_dates": [d.isoformat() for d in comp_dates],
                "comparative_total_transactions": comp_total,
                "comparative_daily_avg_transactions": comp_avg_txn,
                "relative_comparison": {
                    "reference_count": ref_count,
                    "comparative_avg": comp_avg_txn,
                    "absolute_difference": abs_diff,
                    "percentage_difference": pct_diff,
                },
                "trend_direction": trend_dir,
            },
            headline_answer=headline,
            key_finding=(
                f"{parsed.isoformat()} had {ref_count:,} transactions vs comparative average of "
                f"{comp_avg_txn:,.0f} ({comp_label}) — {trend_dir}."
            ),
            date_context_statement=f"{parsed.isoformat()} compared to {comp_label}.",
            above_or_below=trend_dir,
            executive_narrative=(
                f"On {parsed.isoformat()}, {ref_count:,} transactions were processed. "
                f"Compared to the {comp_label} average of {comp_avg_txn:,.0f}/day, this is "
                f"{abs(pct_diff):.1f}% {'higher' if pct_diff > 0 else 'lower'}. Trend direction: {trend_dir}."
            ),
            date_parsed_as=f"{parsed.isoformat()} (parsed from '{ref_str}')",
            fmt_detected=fmt_detected,
            parse_note=parse_note,
        )

    # ------------------------------------------------------------------
    # date_distribution
    # ------------------------------------------------------------------

    def _query_date_distribution(self, params: Dict) -> str:
        """Show how transaction volume and metrics are distributed across all dates."""
        filters = params.get("filters", [])
        include_benchmarks = params.get("include_benchmarks", True)

        metric_per_date = self._compute_metric_per_date("volume", filters)
        vals = list(metric_per_date.values())
        vals_arr = np.array(vals, dtype=float)

        dist_stats = {}
        for label, series in [
            ("volume", vals_arr),
            ("failure_rate", np.array([self._daily_failure_series.get(d, 0) for d in metric_per_date.keys()])),
            ("fraud_rate", np.array([self._daily_fraud_series.get(d, 0) for d in metric_per_date.keys()])),
        ]:
            if len(series) > 0:
                dist_stats[label] = {
                    "min": round(float(np.min(series)), 2),
                    "max": round(float(np.max(series)), 2),
                    "mean": round(float(np.mean(series)), 2),
                    "median": round(float(np.median(series)), 2),
                    "std": round(float(np.std(series, ddof=1)), 2) if len(series) > 1 else 0.0,
                    "p25": round(float(np.percentile(series, 25)), 2),
                    "p75": round(float(np.percentile(series, 75)), 2),
                    "p90": round(float(np.percentile(series, 90)), 2),
                    "p95": round(float(np.percentile(series, 95)), 2),
                }
            else:
                dist_stats[label] = {}

        # Volume histogram (10 bins)
        if len(vals) > 0:
            hist_counts, bin_edges = np.histogram(vals_arr, bins=10)
            histogram: List[Dict] = []
            for i in range(len(hist_counts)):
                histogram.append({
                    "bin_start": round(float(bin_edges[i]), 0),
                    "bin_end": round(float(bin_edges[i + 1]), 0),
                    "date_count": int(hist_counts[i]),
                })
        else:
            histogram = []

        # Day-of-week averages
        dow_avgs: Dict[str, float] = {}
        for dow_num, dow_name in self.DAY_NAMES.items():
            dow_dates = [d for d in metric_per_date if d.weekday() == dow_num]
            if dow_dates:
                dow_avgs[dow_name] = round(float(np.mean([metric_per_date[d] for d in dow_dates])), 2)
            else:
                dow_avgs[dow_name] = 0.0

        # Monthly averages
        monthly_avgs: Dict[str, float] = {}
        from collections import defaultdict
        month_groups: Dict[str, List[float]] = defaultdict(list)
        for d, v in metric_per_date.items():
            key = f"{d.year}-{d.month:02d}"
            month_groups[key].append(v)
        for k, vs in sorted(month_groups.items()):
            monthly_avgs[k] = round(float(np.mean(vs)), 2)

        # Highest / lowest
        sorted_dates = sorted(metric_per_date.items(), key=lambda x: x[1], reverse=True)
        highest = sorted_dates[0] if sorted_dates else (None, 0)
        lowest = sorted_dates[-1] if sorted_dates else (None, 0)

        # Most consistent / volatile metric
        cv_map: Dict[str, float] = {}
        for label, s in dist_stats.items():
            if s and s.get("mean", 0) > 0:
                cv_map[label] = round(s["std"] / s["mean"], 4)
        most_consistent = min(cv_map, key=cv_map.get) if cv_map else "N/A"
        most_volatile = max(cv_map, key=cv_map.get) if cv_map else "N/A"

        headline = f"Transaction volume across {len(metric_per_date)} dates ranges from {int(min(vals)):,} to {int(max(vals)):,}, averaging {int(np.mean(vals)):,} per day."

        return self._wrap_response(
            success=True,
            query_type="date_distribution",
            date_scope=f"All {len(metric_per_date)} dates in dataset",
            filters_applied=filters,
            date_not_in_dataset=False,
            primary_result={
                "distribution_statistics": dist_stats,
                "volume_histogram": histogram,
            },
            hourly_breakdown=None,
            include_benchmarks=include_benchmarks,
            mode_specific_output={
                "day_of_week_averages": dow_avgs,
                "monthly_averages": monthly_avgs,
                "highest_volume_date": {"date": highest[0].isoformat() if highest[0] else None, "count": int(highest[1])},
                "lowest_volume_date": {"date": lowest[0].isoformat() if lowest[0] else None, "count": int(lowest[1])},
                "most_consistent_metric": most_consistent,
                "most_volatile_metric": most_volatile,
            },
            headline_answer=headline,
            key_finding=headline,
            date_context_statement=f"Distribution computed across {len(metric_per_date)} unique dates.",
            above_or_below="N/A",
            executive_narrative=(
                f"Across {len(metric_per_date)} dates, daily transaction volume ranged from "
                f"{int(min(vals)):,} to {int(max(vals)):,} (avg {int(np.mean(vals)):,}). "
                f"Most consistent metric: {most_consistent}. Most volatile: {most_volatile}."
            ),
            date_parsed_as="all dates",
            fmt_detected="N/A",
            parse_note="",
        )

    # ------------------------------------------------------------------
    # weekday_vs_weekend_by_date
    # ------------------------------------------------------------------

    def _query_weekday_vs_weekend_by_date(self, params: Dict) -> str:
        """Compare actual weekend dates vs weekday dates within a range."""
        start_str = params.get("start_date", "")
        end_str = params.get("end_date", "")
        filters = params.get("filters", [])

        if start_str and end_str:
            s_parsed, _, _ = self._parse_date_string(start_str)
            e_parsed, _, _ = self._parse_date_string(end_str)
            if s_parsed is None or e_parsed is None:
                return self._build_date_parse_error(start_str or end_str, "weekday_vs_weekend_by_date")
            if s_parsed > e_parsed:
                s_parsed, e_parsed = e_parsed, s_parsed
        else:
            s_parsed = self.date_range_start
            e_parsed = self.date_range_end

        # Also support month/year shorthand
        month = params.get("month")
        year = params.get("year")
        if month and year:
            month, year = int(month), int(year)
            s_parsed = date(year, month, 1)
            _, ld = calendar.monthrange(year, month)
            e_parsed = date(year, month, ld)

        dates_in_range = [d for d in self.all_dates if s_parsed <= d <= e_parsed]
        weekend_dates = [d for d in dates_in_range if self.date_to_weekend_map.get(d, False)]
        weekday_dates = [d for d in dates_in_range if not self.date_to_weekend_map.get(d, False)]

        df_range = self._filter_to_date_range(s_parsed, e_parsed, filters)

        def _group_stats(date_list: List[date]) -> Dict:
            date_set = set(date_list)
            sub = df_range[df_range["transaction_date"].isin(date_set)]
            daily_counts = []
            daily_fail = []
            daily_fraud = []
            daily_amt = []
            for d in date_list:
                dd = sub[sub["transaction_date"] == d]
                n = len(dd)
                daily_counts.append(n)
                daily_fail.append(dd["transaction_status"].eq("FAILED").sum() / max(n, 1) * 100)
                daily_fraud.append(dd["fraud_flag"].sum() / max(n, 1) * 100)
                daily_amt.append(float(dd["amount_inr"].sum()))

            total = sum(daily_counts)
            return {
                "date_count": len(date_list),
                "dates": [d.isoformat() for d in date_list],
                "total_transactions": total,
                "daily_avg_transactions": round(float(np.mean(daily_counts)), 2) if daily_counts else 0.0,
                "daily_avg_failure_rate_pct": round(float(np.mean(daily_fail)), 2) if daily_fail else 0.0,
                "daily_avg_fraud_rate_pct": round(float(np.mean(daily_fraud)), 2) if daily_fraud else 0.0,
                "daily_avg_amount_inr": round(float(np.mean(daily_amt)), 2) if daily_amt else 0.0,
                "_daily_counts": daily_counts,
            }

        wd_stats = _group_stats(weekday_dates)
        we_stats = _group_stats(weekend_dates)

        # T-test
        p_value = None
        is_significant = False
        if len(wd_stats["_daily_counts"]) > 1 and len(we_stats["_daily_counts"]) > 1:
            t_stat, p_value = scipy_stats.ttest_ind(wd_stats["_daily_counts"], we_stats["_daily_counts"])
            p_value = round(float(p_value), 6)
            is_significant = p_value < 0.05

        # Remove internal field
        del wd_stats["_daily_counts"]
        del we_stats["_daily_counts"]

        # Best in each group
        best_wd = max(((d, int(self._daily_counts_series.get(d, 0))) for d in weekday_dates), key=lambda x: x[1], default=(None, 0))
        best_we = max(((d, int(self._daily_counts_series.get(d, 0))) for d in weekend_dates), key=lambda x: x[1], default=(None, 0))

        headline = (
            f"Weekdays averaged {wd_stats['daily_avg_transactions']:,.0f} txns/day vs weekends at "
            f"{we_stats['daily_avg_transactions']:,.0f} between {s_parsed.isoformat()} and {e_parsed.isoformat()}."
        )

        return self._wrap_response(
            success=True,
            query_type="weekday_vs_weekend_by_date",
            date_scope=f"{s_parsed.isoformat()} to {e_parsed.isoformat()}",
            filters_applied=filters,
            date_not_in_dataset=False,
            primary_result={
                "weekday_stats": wd_stats,
                "weekend_stats": we_stats,
            },
            hourly_breakdown=None,
            include_benchmarks=True,
            mode_specific_output={
                "statistical_comparison": {
                    "p_value": p_value,
                    "is_significant": is_significant,
                },
                "best_weekday_date": {"date": best_wd[0].isoformat() if best_wd[0] else None, "count": best_wd[1]},
                "best_weekend_date": {"date": best_we[0].isoformat() if best_we[0] else None, "count": best_we[1]},
            },
            headline_answer=headline,
            key_finding=headline,
            date_context_statement=f"Compared {len(weekday_dates)} weekday dates vs {len(weekend_dates)} weekend dates.",
            above_or_below="N/A",
            executive_narrative=(
                f"Between {s_parsed.isoformat()} and {e_parsed.isoformat()}, weekdays ({len(weekday_dates)} days) averaged "
                f"{wd_stats['daily_avg_transactions']:,.0f} transactions/day while weekends ({len(weekend_dates)} days) "
                f"averaged {we_stats['daily_avg_transactions']:,.0f}. The difference is "
                f"{'statistically significant' if is_significant else 'not statistically significant'} (p={p_value})."
            ),
            date_parsed_as=f"{s_parsed.isoformat()} to {e_parsed.isoformat()}",
            fmt_detected="range",
            parse_note="",
        )

    # ------------------------------------------------------------------
    # date_anomaly
    # ------------------------------------------------------------------

    def _query_date_anomaly(self, params: Dict) -> str:
        """Identify dates where metrics deviate significantly from daily averages."""
        threshold = float(params.get("anomaly_threshold_multiplier", 1.5))
        filters = params.get("filters", [])
        include_benchmarks = params.get("include_benchmarks", True)

        # Per-date metrics
        metric_per_date_vol = self._compute_metric_per_date("volume", filters)
        metric_per_date_fail = self._compute_metric_per_date("failure_rate", filters)
        metric_per_date_fraud = self._compute_metric_per_date("fraud_rate", filters)

        anomalies: List[Dict] = []

        metric_defs = [
            ("volume", metric_per_date_vol, self.daily_avg_transactions, self.daily_std_transactions),
        ]

        # Compute mean/std for failure and fraud
        fail_vals = list(metric_per_date_fail.values())
        fraud_vals = list(metric_per_date_fraud.values())
        fail_mean = float(np.mean(fail_vals)) if fail_vals else 0.0
        fail_std = float(np.std(fail_vals, ddof=1)) if len(fail_vals) > 1 else 0.0
        fraud_mean = float(np.mean(fraud_vals)) if fraud_vals else 0.0
        fraud_std = float(np.std(fraud_vals, ddof=1)) if len(fraud_vals) > 1 else 0.0

        metric_defs.append(("failure_rate", metric_per_date_fail, fail_mean, fail_std))
        metric_defs.append(("fraud_rate", metric_per_date_fraud, fraud_mean, fraud_std))

        for metric_name, per_date, mean_val, std_val in metric_defs:
            if std_val == 0:
                continue
            for d, val in per_date.items():
                z = (val - mean_val) / std_val
                if abs(z) >= threshold:
                    direction = "Unusually High" if z > 0 else "Unusually Low"
                    pct_above = round((val - mean_val) / mean_val * 100, 1) if mean_val else 0.0

                    if metric_name == "volume":
                        if z > 0:
                            label = f"Volume Surge — {abs(pct_above):.0f}% above average"
                        else:
                            label = f"Volume Drop — {abs(pct_above):.0f}% below average"
                    elif metric_name == "failure_rate":
                        label = f"Elevated Failures — {abs(pct_above):.0f}% above average failure rate" if z > 0 else f"Low Failures — {abs(pct_above):.0f}% below average"
                    elif metric_name == "fraud_rate":
                        label = f"Elevated Fraud — {abs(pct_above):.0f}% above average fraud rate" if z > 0 else f"Low Fraud — {abs(pct_above):.0f}% below average"
                    else:
                        label = direction

                    anomalies.append({
                        "date": d.isoformat(),
                        "day_of_week_label": self.date_to_dayofweek_map.get(d, ""),
                        "is_weekend": self.date_to_weekend_map.get(d, False),
                        "metric": metric_name,
                        "value": round(val, 2),
                        "dataset_average": round(mean_val, 2),
                        "z_score": round(z, 3),
                        "direction": direction,
                        "anomaly_type_label": label,
                    })

        # Sort by abs z-score descending
        anomalies.sort(key=lambda x: abs(x["z_score"]), reverse=True)

        total_anom_dates = len(set(a["date"] for a in anomalies))
        concentration = round(total_anom_dates / max(self.total_days_in_dataset, 1) * 100, 2)

        headline = f"{total_anom_dates} anomalous dates detected (threshold: {threshold}σ), covering {concentration:.1f}% of all dates."

        return self._wrap_response(
            success=True,
            query_type="date_anomaly",
            date_scope=f"All {self.total_days_in_dataset} dates, threshold={threshold}σ",
            filters_applied=filters,
            date_not_in_dataset=False,
            primary_result={
                "anomalies": anomalies,
                "total_anomalous_dates": total_anom_dates,
                "anomaly_concentration_pct": concentration,
            },
            hourly_breakdown=None,
            include_benchmarks=include_benchmarks,
            mode_specific_output={
                "threshold_used": threshold,
                "metrics_checked": ["volume", "failure_rate", "fraud_rate"],
            },
            headline_answer=headline,
            key_finding=headline,
            date_context_statement=f"Anomaly detection across {self.total_days_in_dataset} dates using {threshold}σ threshold.",
            above_or_below="N/A",
            executive_narrative=(
                f"Anomaly detection flagged {total_anom_dates} dates ({concentration:.1f}% of all dates) where metrics "
                f"deviated by more than {threshold}σ from the daily average. "
                + (f"The most extreme anomaly was on {anomalies[0]['date']} ({anomalies[0]['anomaly_type_label']}, z={anomalies[0]['z_score']:.2f})." if anomalies else "No significant anomalies found.")
            ),
            date_parsed_as="all dates",
            fmt_detected="N/A",
            parse_note="",
        )

    # ==================================================================
    # INTERNAL HELPER METHODS
    # ==================================================================

    # ------------------------------------------------------------------
    # Date parsing
    # ------------------------------------------------------------------

    def _parse_date_string(self, date_str: str) -> Tuple[Optional[date], str, str]:
        """
        Parse a date string using flexible format detection.

        Attempts multiple formats in order of likelihood.  Falls back to
        pandas.to_datetime with format inference.

        Args:
            date_str: Raw date string from the user / LLM.

        Returns:
            Tuple of (parsed date | None, format detected description, note).
        """
        if not date_str or not str(date_str).strip():
            return None, "", "Empty date string"

        raw = str(date_str).strip()

        # Strip ordinal suffixes (1st, 2nd, 3rd, 4th, …)
        import re
        cleaned = re.sub(r'(\d+)(st|nd|rd|th)\b', r'\1', raw)

        # Try explicit formats
        for fmt in self._DATE_FORMATS:
            try:
                parsed = datetime.strptime(cleaned, fmt).date()
                # Sanity: if year is missing (< 100), assume current dataset year range
                if parsed.year < 100:
                    parsed = parsed.replace(year=parsed.year + 2000)
                return parsed, fmt, ""
            except (ValueError, TypeError):
                continue

        # Fallback: pandas flexible parser
        try:
            parsed = pd.to_datetime(cleaned, dayfirst=False).date()
            return parsed, "pandas_inferred", "Parsed via pandas flexible parser"
        except Exception:
            pass

        try:
            parsed = pd.to_datetime(cleaned, dayfirst=True).date()
            return parsed, "pandas_inferred_dayfirst", "Parsed via pandas with dayfirst=True"
        except Exception:
            pass

        return None, "", f"Could not parse date: '{raw}'"

    # ------------------------------------------------------------------
    # Date validation
    # ------------------------------------------------------------------

    def _validate_date(self, parsed: date, query_type: str, raw_str: str, fmt: str) -> Tuple[bool, Optional[str]]:
        """
        Validate that a parsed date exists in the dataset.

        Returns (True, None) if valid, or (False, error_response_json) if not.
        """
        if parsed in set(self.all_dates):
            return True, None

        return False, self._build_date_not_found_response(parsed, query_type, raw_str, fmt)

    def _build_date_not_found_response(self, parsed: date, query_type: str, raw_str: str, fmt: str) -> str:
        """Build a structured response for a date not found in the dataset."""
        # Find nearest available date
        nearest = min(self.all_dates, key=lambda d: abs((d - parsed).days)) if self.all_dates else None
        suggestion = (
            f"The dataset contains dates from {self.date_range_start.isoformat()} to "
            f"{self.date_range_end.isoformat()}. The requested date {parsed.isoformat()} has no transactions."
        )
        if nearest:
            suggestion += f" The closest available date is {nearest.isoformat()}."

        return json.dumps({
            "success": True,
            "query_type": query_type,
            "date_scope": f"Requested: {parsed.isoformat()}",
            "date_not_in_dataset": True,
            "total_transactions": 0,
            "dataset_date_range": {
                "earliest_date": self.date_range_start.isoformat() if self.date_range_start else None,
                "latest_date": self.date_range_end.isoformat() if self.date_range_end else None,
                "total_days_in_dataset": self.total_days_in_dataset,
            },
            "suggestion": suggestion,
            "summary": {
                "headline_answer": f"0 transactions occurred on {parsed.isoformat()} — this date is not in the dataset.",
                "key_finding": suggestion,
                "date_context_statement": suggestion,
                "above_or_below_average": "N/A",
                "executive_narrative": suggestion,
            },
            "metadata": {
                "date_parsed_as": f"{parsed.isoformat()} (parsed from '{raw_str}')",
                "date_format_detected": fmt,
                "timestamp_column_used": "timestamp",
                "date_extraction_method": "pd.to_datetime().dt.date",
                "benchmark_source": "cached_at_initialization",
                "execution_note": f"Requested date {parsed.isoformat()} is not in the dataset.",
            },
        }, default=str)

    def _build_date_parse_error(self, raw_str: str, query_type: str) -> str:
        """Build a structured error for a date that could not be parsed."""
        return json.dumps({
            "success": False,
            "query_type": query_type,
            "date_not_in_dataset": False,
            "error": f"Could not parse date string: '{raw_str}'",
            "dataset_date_range": {
                "earliest_date": self.date_range_start.isoformat() if self.date_range_start else None,
                "latest_date": self.date_range_end.isoformat() if self.date_range_end else None,
            },
            "suggestion": f"Please provide the date in YYYY-MM-DD format (e.g., {self.date_range_start.isoformat() if self.date_range_start else '2024-12-30'}).",
        }, default=str)

    # ------------------------------------------------------------------
    # Data filtering
    # ------------------------------------------------------------------

    def _filter_to_date(self, target: date, filters: List[Dict] = None) -> pd.DataFrame:
        """Filter the working DataFrame to a single date, with optional additional filters."""
        df = self.df[self.df["transaction_date"] == target]
        if filters:
            df = self._apply_filters(df, filters)
        return df

    def _filter_to_date_range(self, start: date, end: date, filters: List[Dict] = None) -> pd.DataFrame:
        """Filter the working DataFrame to a date range, with optional additional filters."""
        df = self.df[(self.df["transaction_date"] >= start) & (self.df["transaction_date"] <= end)]
        if filters:
            df = self._apply_filters(df, filters)
        return df

    def _apply_filters(self, df: pd.DataFrame, filters: List[Dict]) -> pd.DataFrame:
        """Apply a list of filter conditions to *df* and return the subset."""
        for f in filters:
            col = data_loader.resolve_column(f.get("column", ""))
            op = f.get("operator", "==")
            val = f.get("value")
            if col not in df.columns:
                continue
            if op == "==":
                df = df[df[col] == val]
            elif op == "!=":
                df = df[df[col] != val]
            elif op == ">":
                df = df[df[col] > val]
            elif op == "<":
                df = df[df[col] < val]
            elif op == ">=":
                df = df[df[col] >= val]
            elif op == "<=":
                df = df[df[col] <= val]
            elif op == "in":
                df = df[df[col].isin(val)]
        return df

    # ------------------------------------------------------------------
    # Core metrics computation
    # ------------------------------------------------------------------

    def _compute_date_metrics(
        self,
        df: pd.DataFrame,
        target_date: date,
        include_benchmarks: bool = True,
        include_type_breakdown: bool = True,
    ) -> Dict[str, Any]:
        """
        Compute the complete date metrics block for a given filtered DataFrame.

        This is the standard metric set used consistently across all query types.

        Args:
            df: DataFrame already filtered to the target date (and any additional filters).
            target_date: The calendar date being analyzed.
            include_benchmarks: Whether to append dataset-wide benchmark comparisons.
            include_type_breakdown: Whether to include transaction type counts.

        Returns:
            Dictionary with every metric defined in the Complete Date Metrics Block spec.
        """
        n = len(df)
        metrics: Dict[str, Any] = {}

        # Core Count
        metrics["total_transactions"] = n
        metrics["total_transactions_formatted"] = f"{n:,}"

        if n == 0:
            # Return zeroed metrics for empty date
            return self._empty_date_metrics(target_date)

        # Status breakdown
        status = df["transaction_status"].value_counts()
        success = int(status.get("SUCCESS", 0))
        failed = int(status.get("FAILED", 0))
        pending = int(status.get("PENDING", 0))

        metrics["success_count"] = success
        metrics["success_rate_pct"] = round(success / n * 100, 2)
        metrics["failed_count"] = failed
        metrics["failure_rate_pct"] = round(failed / n * 100, 2)
        metrics["pending_count"] = pending
        metrics["pending_rate_pct"] = round(pending / n * 100, 2)

        # Amount metrics
        amt = df["amount_inr"].dropna()
        metrics["total_amount_inr"] = round(float(amt.sum()), 2)
        metrics["avg_amount_inr"] = round(float(amt.mean()), 2) if len(amt) > 0 else 0.0
        metrics["median_amount_inr"] = round(float(amt.median()), 2) if len(amt) > 0 else 0.0
        metrics["max_amount_inr"] = round(float(amt.max()), 2) if len(amt) > 0 else 0.0
        metrics["min_amount_inr"] = round(float(amt.min()), 2) if len(amt) > 0 else 0.0

        # Fraud metrics
        fraud_ct = int(df["fraud_flag"].sum())
        metrics["fraud_flagged_count"] = fraud_ct
        metrics["fraud_rate_pct"] = round(fraud_ct / n * 100, 2)

        # Calendar context
        metrics["date"] = target_date.isoformat()
        dow_num = target_date.weekday()
        metrics["day_of_week_label"] = self.DAY_NAMES.get(dow_num, "")
        metrics["day_of_week_number"] = dow_num
        metrics["is_weekend"] = dow_num >= 5
        metrics["is_weekend_label"] = "Weekend" if dow_num >= 5 else "Weekday"

        # Benchmark context
        if include_benchmarks:
            vs_avg = round(n - self.daily_avg_transactions, 2)
            vs_pct = round(vs_avg / self.daily_avg_transactions * 100, 2) if self.daily_avg_transactions else 0.0
            rank = self.date_to_rank_map.get(target_date, self.total_days_in_dataset)
            percentile = round((1 - rank / max(self.total_days_in_dataset, 1)) * 100, 2)

            metrics["vs_daily_avg_transactions"] = vs_avg
            metrics["vs_daily_avg_pct"] = vs_pct
            metrics["date_rank"] = rank
            metrics["date_percentile"] = percentile

        # Transaction type breakdown
        if include_type_breakdown:
            types = df["transaction_type"].value_counts()
            metrics["p2p_count"] = int(types.get("P2P", 0))
            metrics["p2m_count"] = int(types.get("P2M", 0))
            metrics["bill_payment_count"] = int(types.get("Bill Payment", 0))
            metrics["recharge_count"] = int(types.get("Recharge", 0))
            counts_by_type = {"P2P": metrics["p2p_count"], "P2M": metrics["p2m_count"],
                              "Bill Payment": metrics["bill_payment_count"], "Recharge": metrics["recharge_count"]}
            metrics["dominant_transaction_type"] = max(counts_by_type, key=counts_by_type.get)

        return metrics

    def _empty_date_metrics(self, target_date: date) -> Dict[str, Any]:
        """Return zeroed-out metrics for a date with no transactions."""
        dow_num = target_date.weekday()
        return {
            "total_transactions": 0,
            "total_transactions_formatted": "0",
            "success_count": 0, "success_rate_pct": 0.0,
            "failed_count": 0, "failure_rate_pct": 0.0,
            "pending_count": 0, "pending_rate_pct": 0.0,
            "total_amount_inr": 0.0, "avg_amount_inr": 0.0,
            "median_amount_inr": 0.0, "max_amount_inr": 0.0, "min_amount_inr": 0.0,
            "fraud_flagged_count": 0, "fraud_rate_pct": 0.0,
            "date": target_date.isoformat(),
            "day_of_week_label": self.DAY_NAMES.get(dow_num, ""),
            "day_of_week_number": dow_num,
            "is_weekend": dow_num >= 5,
            "is_weekend_label": "Weekend" if dow_num >= 5 else "Weekday",
            "vs_daily_avg_transactions": round(-self.daily_avg_transactions, 2),
            "vs_daily_avg_pct": -100.0,
            "date_rank": self.total_days_in_dataset,
            "date_percentile": 0.0,
            "p2p_count": 0, "p2m_count": 0, "bill_payment_count": 0, "recharge_count": 0,
            "dominant_transaction_type": "N/A",
        }

    # ------------------------------------------------------------------
    # Hourly breakdown
    # ------------------------------------------------------------------

    def _compute_hourly_breakdown(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Compute 24-hour transaction breakdown for a filtered DataFrame.

        Uses the pre-derived hour_of_day column — never re-derives from timestamp.
        Always returns all 24 hours including those with zero transactions.
        """
        hourly: List[Dict[str, Any]] = []
        if len(df) == 0:
            for h in range(24):
                hourly.append({
                    "hour": h, "hour_label": self.HOUR_LABELS[h],
                    "transaction_count": 0, "total_amount_inr": 0.0,
                    "failure_rate_pct": 0.0, "success_count": 0, "failed_count": 0,
                })
            return hourly

        grouped = df.groupby("hour_of_day")
        for h in range(24):
            if h in grouped.groups:
                g = grouped.get_group(h)
                n = len(g)
                success = int(g["transaction_status"].eq("SUCCESS").sum())
                failed = int(g["transaction_status"].eq("FAILED").sum())
                total_amt = round(float(g["amount_inr"].sum()), 2)
                fail_rate = round(failed / n * 100, 2) if n > 0 else 0.0
            else:
                n, success, failed, total_amt, fail_rate = 0, 0, 0, 0.0, 0.0

            hourly.append({
                "hour": h,
                "hour_label": self.HOUR_LABELS[h],
                "transaction_count": n,
                "total_amount_inr": total_amt,
                "failure_rate_pct": fail_rate,
                "success_count": success,
                "failed_count": failed,
            })
        return hourly

    # ------------------------------------------------------------------
    # Peak / slowest hour
    # ------------------------------------------------------------------

    def _compute_peak_slowest_hour(self, df: pd.DataFrame) -> Tuple[Optional[Dict], Optional[Dict]]:
        """Identify the peak and slowest hour on a specific date's data."""
        if len(df) == 0:
            return None, None

        counts = df.groupby("hour_of_day").size()
        peak_h = int(counts.idxmax())
        slowest_h = int(counts.idxmin())
        return (
            {"hour": peak_h, "hour_label": self.HOUR_LABELS[peak_h], "count": int(counts[peak_h])},
            {"hour": slowest_h, "hour_label": self.HOUR_LABELS[slowest_h], "count": int(counts[slowest_h])},
        )

    # ------------------------------------------------------------------
    # Metric computation per date
    # ------------------------------------------------------------------

    def _compute_metric_per_date(self, metric: str, filters: List[Dict] = None) -> Dict[date, float]:
        """Compute a single metric for every date in the dataset."""
        df = self.df.copy()
        if filters:
            df = self._apply_filters(df, filters)

        result: Dict[date, float] = {}

        if metric == "volume":
            counts = df.groupby("transaction_date").size()
            for d in self.all_dates:
                result[d] = float(counts.get(d, 0))
        elif metric == "total_amount":
            sums = df.groupby("transaction_date")["amount_inr"].sum()
            for d in self.all_dates:
                result[d] = round(float(sums.get(d, 0)), 2)
        elif metric == "avg_amount":
            means = df.groupby("transaction_date")["amount_inr"].mean()
            for d in self.all_dates:
                result[d] = round(float(means.get(d, 0)), 2)
        elif metric == "failure_rate":
            for d in self.all_dates:
                dd = df[df["transaction_date"] == d]
                n = len(dd)
                result[d] = round(dd["transaction_status"].eq("FAILED").sum() / max(n, 1) * 100, 2)
        elif metric == "fraud_rate":
            for d in self.all_dates:
                dd = df[df["transaction_date"] == d]
                n = len(dd)
                result[d] = round(float(dd["fraud_flag"].sum()) / max(n, 1) * 100, 2)
        elif metric == "success_rate":
            for d in self.all_dates:
                dd = df[df["transaction_date"] == d]
                n = len(dd)
                result[d] = round(dd["transaction_status"].eq("SUCCESS").sum() / max(n, 1) * 100, 2)
        else:
            # Default to volume
            counts = df.groupby("transaction_date").size()
            for d in self.all_dates:
                result[d] = float(counts.get(d, 0))

        return result

    # ------------------------------------------------------------------
    # Benchmark helpers
    # ------------------------------------------------------------------

    def _compute_vs_benchmark(self, value: float, benchmark: float) -> Dict[str, float]:
        """Compute absolute and percentage difference from a benchmark."""
        diff = round(value - benchmark, 2)
        pct = round(diff / benchmark * 100, 2) if benchmark else 0.0
        return {"absolute_difference": diff, "percentage_difference": pct}

    def _get_date_rank(self, target: date) -> int:
        """Return the volume rank for a date (1 = busiest)."""
        return self.date_to_rank_map.get(target, self.total_days_in_dataset)

    def _above_or_below(self, pct: float) -> str:
        """Return Above/Below/At Average label based on percentage difference."""
        if pct > 5:
            return "Above Average"
        elif pct < -5:
            return "Below Average"
        return "At Average"

    # ------------------------------------------------------------------
    # Headline answer generator (MOST CRITICAL METHOD)
    # ------------------------------------------------------------------

    def _generate_headline_answer(self, query_type: str, **kwargs) -> str:
        """
        Generate the factually accurate headline answer.

        This is the single most critical output field — it prevents hallucination
        by providing a ready-made, precisely numbered statement derived from actual
        computed data.

        Args:
            query_type: The query type being served.
            **kwargs: Query-type-specific data for headline construction.

        Returns:
            A single plain-English sentence with precise numbers.
        """
        if query_type == "single_date":
            total = kwargs.get("total_txn", 0)
            d = kwargs.get("date_val")
            dow = kwargs.get("dow", "")
            return f"{total:,} transactions occurred on {d.isoformat()} ({dow})."

        if query_type == "date_range":
            total = kwargs.get("total_txn", 0)
            start = kwargs.get("start")
            end = kwargs.get("end")
            n_days = kwargs.get("n_days", 0)
            return (
                f"{total:,} transactions occurred between {start.isoformat()} and "
                f"{end.isoformat()} across {n_days} days."
            )

        if query_type == "month_breakdown":
            total = kwargs.get("total_txn", 0)
            label = kwargs.get("month_label", "")
            avg = kwargs.get("daily_avg", 0)
            return f"{total:,} transactions occurred in {label}, averaging {avg:,.0f} per day."

        if query_type == "date_comparison":
            infos = kwargs.get("dates_info", [])
            if len(infos) == 2:
                d1, c1 = infos[0]
                d2, c2 = infos[1]
                diff = abs(c1 - c2)
                higher = d1 if c1 > c2 else d2
                pct = round(diff / max(min(c1, c2), 1) * 100, 1)
                return (
                    f"{d1} had {c1:,} transactions vs {d2} with {c2:,} — "
                    f"a difference of {diff:,} ({pct}% higher on {higher})."
                )
            parts = [f"{d}: {c:,}" for d, c in infos]
            return "Transaction counts — " + ", ".join(parts) + "."

        if query_type == "date_ranking":
            top = kwargs.get("top_date")
            bottom = kwargs.get("bottom_date")
            metric = kwargs.get("metric", "volume")
            if top and bottom:
                td, tv = top
                bd, bv = bottom
                return (
                    f"The busiest date was {td.isoformat()} ({self.date_to_dayofweek_map.get(td, '')}) "
                    f"with {int(tv):,} transactions. The quietest was {bd.isoformat()} with {int(bv):,}."
                )
            return "No dates found for ranking."

        return ""

    # ------------------------------------------------------------------
    # Context statement & narrative generators
    # ------------------------------------------------------------------

    def _generate_date_context_statement(self, target: date, count: int) -> str:
        """Generate a plain-English sentence placing this date in context."""
        dow = self.date_to_dayofweek_map.get(target, "")
        vs_pct = round((count - self.daily_avg_transactions) / self.daily_avg_transactions * 100, 1) if self.daily_avg_transactions else 0
        direction = "above" if vs_pct > 0 else ("below" if vs_pct < 0 else "at")
        return (
            f"{target.isoformat()} was a {dow}, with {count:,} transactions — "
            f"{abs(vs_pct):.1f}% {direction} the dataset daily average of "
            f"{self.daily_avg_transactions:,.0f}"
        )

    def _generate_executive_narrative(self, target: date, metrics: Dict) -> str:
        """Generate a 2–3 sentence executive summary."""
        dow = self.date_to_dayofweek_map.get(target, "")
        total = metrics["total_transactions"]
        amount = metrics.get("total_amount_inr", 0)
        fail = metrics.get("failure_rate_pct", 0)
        fraud = metrics.get("fraud_rate_pct", 0)
        return (
            f"On {target.isoformat()} ({dow}), the platform processed {total:,} transactions "
            f"totaling ₹{amount:,.2f}. The failure rate was {fail:.2f}% and fraud flag rate was {fraud:.2f}%."
        )

    # ------------------------------------------------------------------
    # Calendar helpers
    # ------------------------------------------------------------------

    def _calendar_dates_between(self, start: date, end: date) -> List[date]:
        """Return a list of all calendar dates from start to end inclusive."""
        if start > end:
            return []
        result: List[date] = []
        current = start
        while current <= end:
            result.append(current)
            current += timedelta(days=1)
        return result

    # ------------------------------------------------------------------
    # Response wrapper
    # ------------------------------------------------------------------

    def _wrap_response(
        self,
        success: bool,
        query_type: str,
        date_scope: str,
        filters_applied: List,
        date_not_in_dataset: bool,
        primary_result: Dict,
        hourly_breakdown: Optional[List],
        include_benchmarks: bool,
        mode_specific_output: Dict,
        headline_answer: str,
        key_finding: str,
        date_context_statement: str,
        above_or_below: str,
        executive_narrative: str,
        date_parsed_as: str,
        fmt_detected: str,
        parse_note: str,
    ) -> str:
        """Build the standardised JSON response wrapper."""
        benchmarks = None
        if include_benchmarks:
            benchmarks = {
                "daily_avg_transactions": self.daily_avg_transactions,
                "daily_avg_failure_rate_pct": self.daily_avg_failure_rate,
                "daily_avg_fraud_rate_pct": self.daily_avg_fraud_rate,
                "daily_avg_amount_inr": self.daily_avg_amount,
            }

        response: Dict[str, Any] = {
            "success": success,
            "query_type": query_type,
            "date_scope": date_scope,
            "filters_applied": filters_applied,
            "dataset_date_range": {
                "earliest_date": self.date_range_start.isoformat() if self.date_range_start else None,
                "latest_date": self.date_range_end.isoformat() if self.date_range_end else None,
                "total_days_in_dataset": self.total_days_in_dataset,
            },
            "date_not_in_dataset": date_not_in_dataset,
            "primary_result": primary_result,
        }

        if hourly_breakdown is not None:
            response["hourly_breakdown"] = hourly_breakdown

        if benchmarks is not None:
            response["benchmarks"] = benchmarks

        if mode_specific_output:
            response["mode_specific_output"] = mode_specific_output

        response["summary"] = {
            "headline_answer": headline_answer,
            "key_finding": key_finding,
            "date_context_statement": date_context_statement,
            "above_or_below_average": above_or_below,
            "executive_narrative": executive_narrative,
        }

        response["metadata"] = {
            "date_parsed_as": date_parsed_as,
            "date_format_detected": fmt_detected,
            "timestamp_column_used": "timestamp",
            "date_extraction_method": "pd.to_datetime().dt.date",
            "benchmark_source": "cached_at_initialization",
            "execution_note": parse_note,
        }

        return json.dumps(response, default=str)

    # ------------------------------------------------------------------
    # Error response helper
    # ------------------------------------------------------------------

    def _error_response(self, query_type: str, error: str, suggestion: str) -> str:
        """Build standardised error JSON response."""
        return json.dumps({
            "success": False,
            "query_type": query_type,
            "date_not_in_dataset": False,
            "error": error,
            "dataset_date_range": {
                "earliest_date": self.date_range_start.isoformat() if self.date_range_start else None,
                "latest_date": self.date_range_end.isoformat() if self.date_range_end else None,
            },
            "suggestion": suggestion,
        }, default=str)


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------

def create_date_query_tool() -> StructuredTool:
    """
    Factory function to create the date query tool for LangChain.

    Returns:
        StructuredTool configured for calendar-date-level transaction analysis.
    """
    tool_instance = DateQueryTool()

    return StructuredTool.from_function(
        func=tool_instance.query,
        name="date_query_tool",
        description=(
            "Use this tool for ALL questions involving specific calendar dates, date ranges, "
            "months, or any query where the user mentions an actual date like '2024-12-30' or "
            "'December' or 'last week.' This is the ONLY tool in the system that can filter by "
            "calendar date — no other tool can do this. Use query_type 'single_date' for specific "
            "date questions, 'date_range' for date spans, 'month_breakdown' for month queries, "
            "'date_comparison' for comparing specific dates, 'date_ranking' for finding busiest/"
            "quietest dates. Input: query_type (string) and parameters (JSON string with date, "
            "start_date, end_date, month, year, metric, filters, include_hourly_breakdown)."
        ),
        args_schema=DateQueryInput,
    )
