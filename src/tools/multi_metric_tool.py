"""
Multi-Metric Tool for PayInsight AI

This module provides a single-pass, vectorized multi-KPI computation engine for
transaction data. It computes the entire metric catalog — volume, amount, status,
fraud, efficiency, and distribution metrics — in one DataFrame pass, eliminating
redundant scans required when calling individual tools separately.

Supports 10 analysis modes: snapshot, grouped_snapshot, multi_group_snapshot,
segment_profile, health_scorecard, transaction_type_profile, temporal_snapshot,
funnel_analysis, anomaly_snapshot, and comparative_snapshot.

Author: Team primeFactors
"""

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
import pandas as pd
import numpy as np
import json
import math
import time
from typing import Any, Dict, List, Optional, Tuple
from src.utils.data_loader import data_loader


# ---------------------------------------------------------------------------
# Input schema
# ---------------------------------------------------------------------------

class MultiMetricInput(BaseModel):
    """Input schema for multi_metric_tool."""

    analysis_mode: str = Field(
        description=(
            "Which computation profile to use: snapshot, grouped_snapshot, "
            "multi_group_snapshot, segment_profile, health_scorecard, "
            "transaction_type_profile, temporal_snapshot, funnel_analysis, "
            "anomaly_snapshot, comparative_snapshot"
        )
    )
    parameters: str = Field(
        description=(
            "JSON string containing filters, group_by, metrics_to_include, "
            "metrics_to_exclude, include_benchmarks, include_percentile_context, "
            "benchmark_filters, include_confidence_intervals, flag_threshold_multiplier, "
            "segment_a_filters, segment_b_filters, segment_a_label, segment_b_label"
        )
    )


# ---------------------------------------------------------------------------
# Valid analysis modes
# ---------------------------------------------------------------------------

VALID_MODES = {
    "snapshot",
    "grouped_snapshot",
    "multi_group_snapshot",
    "segment_profile",
    "health_scorecard",
    "transaction_type_profile",
    "temporal_snapshot",
    "funnel_analysis",
    "anomaly_snapshot",
    "comparative_snapshot",
}


# ---------------------------------------------------------------------------
# Core tool class
# ---------------------------------------------------------------------------

class MultiMetricTool:
    """
    Single-pass multi-KPI computation engine.

    Computes the full metric catalog (volume, amount, status, fraud, efficiency,
    distribution) in a single vectorized pandas pass on filtered data. Supports
    10 analysis modes with benchmarking, confidence intervals, anomaly detection,
    health grading, and funnel analysis.

    Attributes:
        df: The full transaction DataFrame loaded from the singleton data_loader.
        total_records: Total row count of the full dataset.
        global_benchmarks: Pre-computed metrics on the full dataset (cached at init).
        global_percentiles: Pre-computed percentile distributions for key metrics.
    """

    def __init__(self) -> None:
        """Initialise the tool and cache global benchmarks."""
        start = time.time()
        self.df: pd.DataFrame = data_loader.load_data()
        self.total_records: int = len(self.df)

        # Pre-compute boolean mask columns once on the full dataset
        self._ensure_mask_columns(self.df)

        # Cache global benchmarks and percentiles
        self.global_benchmarks: Dict[str, Any] = self._compute_metrics_single_pass(self.df)
        self.global_percentiles: Dict[str, Dict[str, float]] = self._compute_global_percentiles()

        elapsed = round((time.time() - start) * 1000, 1)
        print(f"  [MultiMetricTool] Global benchmark cache built in {elapsed}ms")

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def analyze(self, analysis_mode: str, parameters: str) -> str:
        """
        Execute multi-metric analysis.

        Args:
            analysis_mode: One of the 10 supported computation profiles.
            parameters: JSON string with filters, group_by, options.

        Returns:
            JSON string with the complete analysis result.
        """
        try:
            params = json.loads(parameters) if parameters else {}
        except json.JSONDecodeError as exc:
            return self._error_response(analysis_mode, f"Invalid JSON in parameters: {exc}",
                                        "Ensure parameters is a valid JSON string.")

        if analysis_mode not in VALID_MODES:
            return self._error_response(
                analysis_mode,
                f"Unknown analysis_mode '{analysis_mode}'. Valid modes: {sorted(VALID_MODES)}",
                "Choose one of the valid analysis modes."
            )

        dispatch = {
            "snapshot": self._mode_snapshot,
            "grouped_snapshot": self._mode_grouped_snapshot,
            "multi_group_snapshot": self._mode_multi_group_snapshot,
            "segment_profile": self._mode_segment_profile,
            "health_scorecard": self._mode_health_scorecard,
            "transaction_type_profile": self._mode_transaction_type_profile,
            "temporal_snapshot": self._mode_temporal_snapshot,
            "funnel_analysis": self._mode_funnel_analysis,
            "anomaly_snapshot": self._mode_anomaly_snapshot,
            "comparative_snapshot": self._mode_comparative_snapshot,
        }

        try:
            return dispatch[analysis_mode](params)
        except Exception as exc:
            return self._error_response(analysis_mode, str(exc),
                                        "Check your filters and parameters for correctness.")

    # ------------------------------------------------------------------
    # Internal: mask columns
    # ------------------------------------------------------------------

    @staticmethod
    def _ensure_mask_columns(df: pd.DataFrame) -> None:
        """
        Pre-compute boolean mask columns on *df* for single-pass aggregation.

        Args:
            df: DataFrame to augment in-place with mask columns.
        """
        if "_is_success" not in df.columns:
            df["_is_success"] = (df["transaction_status"] == "SUCCESS")
        if "_is_failed" not in df.columns:
            df["_is_failed"] = (df["transaction_status"] == "FAILED")
        if "_is_pending" not in df.columns:
            df["_is_pending"] = (df["transaction_status"] == "PENDING")
        if "_is_fraud" not in df.columns:
            df["_is_fraud"] = df["fraud_flag"].astype(bool)
        if "_success_amount" not in df.columns:
            df["_success_amount"] = df["amount_inr"].where(df["_is_success"], 0.0)
        if "_failed_amount" not in df.columns:
            df["_failed_amount"] = df["amount_inr"].where(df["_is_failed"], 0.0)
        if "_fraud_amount" not in df.columns:
            df["_fraud_amount"] = df["amount_inr"].where(df["_is_fraud"], 0.0)
        if "_clean_success" not in df.columns:
            df["_clean_success"] = df["_is_success"] & (~df["_is_fraud"])
        if "_is_problematic" not in df.columns:
            df["_is_problematic"] = df["_is_failed"] | df["_is_fraud"]

    # ------------------------------------------------------------------
    # Internal: apply filters
    # ------------------------------------------------------------------

    def _apply_filters(self, df: pd.DataFrame, filters: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Apply a list of filter conditions to a DataFrame.

        Args:
            df: Source DataFrame.
            filters: List of dicts with keys column, operator, value.

        Returns:
            Filtered DataFrame (copy).
        """
        if not filters:
            return df

        mask = pd.Series(True, index=df.index)
        for f in filters:
            col = data_loader.resolve_column(f["column"])
            op = f["operator"]
            val = f["value"]

            if col not in df.columns:
                continue

            if op == "==":
                mask &= df[col] == val
            elif op == "!=":
                mask &= df[col] != val
            elif op == ">":
                mask &= df[col] > val
            elif op == "<":
                mask &= df[col] < val
            elif op == ">=":
                mask &= df[col] >= val
            elif op == "<=":
                mask &= df[col] <= val
            elif op == "in":
                mask &= df[col].isin(val)
            elif op == "not_in":
                mask &= ~df[col].isin(val)
            elif op == "contains":
                mask &= df[col].astype(str).str.contains(str(val), case=False, na=False)

        return df.loc[mask]

    # ------------------------------------------------------------------
    # Internal: single-pass metric computation (ungrouped)
    # ------------------------------------------------------------------

    def _compute_metrics_single_pass(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Compute the full metric catalog on *df* in a single aggregation pass.

        Uses one ``agg()`` call for all scalar aggregations, then derives
        rates and efficiency metrics from the aggregated values.

        Args:
            df: The (filtered) DataFrame to compute metrics on.

        Returns:
            Dictionary of all metric key-value pairs.
        """
        n = len(df)
        if n == 0:
            return self._empty_metrics()

        self._ensure_mask_columns(df)

        # --- Single agg() call using dict-of-lists on a column subset ---
        # We build one aggregation dict and call agg() once on the DataFrame.
        agg_spec = {
            "transaction_id": ["count"],
            "amount_inr": ["sum", "mean", "median", "min", "max", "std"],
            "_is_success": ["sum"],
            "_is_failed": ["sum"],
            "_is_pending": ["sum"],
            "_is_fraud": ["sum"],
            "_success_amount": ["sum"],
            "_failed_amount": ["sum"],
            "_fraud_amount": ["sum"],
            "_clean_success": ["sum"],
            "_is_problematic": ["sum"],
            "timestamp": ["nunique"],
        }
        agg_result = df.agg(agg_spec)

        # Extract values from the resulting DataFrame (col, func) index
        m: Dict[str, Any] = {}
        m["total_transactions"] = int(agg_result.loc["count", "transaction_id"])
        m["total_amount_inr"] = float(agg_result.loc["sum", "amount_inr"])
        m["avg_amount_inr"] = float(agg_result.loc["mean", "amount_inr"])
        m["median_amount_inr"] = float(agg_result.loc["median", "amount_inr"])
        m["min_amount_inr"] = float(agg_result.loc["min", "amount_inr"])
        m["max_amount_inr"] = float(agg_result.loc["max", "amount_inr"])
        m["amount_std_inr"] = float(agg_result.loc["std", "amount_inr"]) if not pd.isna(agg_result.loc["std", "amount_inr"]) else 0.0
        m["success_count"] = int(agg_result.loc["sum", "_is_success"])
        m["failed_count"] = int(agg_result.loc["sum", "_is_failed"])
        m["pending_count"] = int(agg_result.loc["sum", "_is_pending"])
        m["fraud_count"] = int(agg_result.loc["sum", "_is_fraud"])
        m["success_amount_total"] = float(agg_result.loc["sum", "_success_amount"])
        m["failed_amount_total"] = float(agg_result.loc["sum", "_failed_amount"])
        m["fraud_amount_total"] = float(agg_result.loc["sum", "_fraud_amount"])
        clean_success_count = int(agg_result.loc["sum", "_clean_success"])
        problematic_count = int(agg_result.loc["sum", "_is_problematic"])
        unique_days_val = int(agg_result.loc["nunique", "timestamp"])

        # Percentiles (vectorised)
        amt = df["amount_inr"].dropna()
        if len(amt) > 0:
            m["p25_amount_inr"] = float(np.percentile(amt, 25))
            m["p75_amount_inr"] = float(np.percentile(amt, 75))
            m["p95_amount_inr"] = float(np.percentile(amt, 95))
        else:
            m["p25_amount_inr"] = 0.0
            m["p75_amount_inr"] = 0.0
            m["p95_amount_inr"] = 0.0

        total = float(m["total_transactions"])
        total_amt = float(m["total_amount_inr"])
        global_total = float(self.total_records)
        global_amt = float(self.df["amount_inr"].sum()) if not hasattr(self, "global_benchmarks") or not self.global_benchmarks else float(self.global_benchmarks.get("total_amount_inr", self.df["amount_inr"].sum()))

        # Volume metrics
        unique_days = max(unique_days_val, 1)
        m["transactions_per_day"] = round(total / unique_days, 2)
        m["transactions_per_hour"] = round(total / 24, 2)
        m["data_share_pct"] = round(total / global_total * 100, 2) if global_total > 0 else 0.0

        # Amount share
        m["amount_share_pct"] = round(total_amt / global_amt * 100, 2) if global_amt > 0 else 0.0
        m["wallet_concentration_ratio"] = round(m["amount_share_pct"] / m["data_share_pct"], 4) if m["data_share_pct"] > 0 else 0.0

        # Status rates
        m["success_rate_pct"] = round(float(m["success_count"]) / total * 100, 2) if total > 0 else 0.0
        m["failure_rate_pct"] = round(float(m["failed_count"]) / total * 100, 2) if total > 0 else 0.0
        m["pending_rate_pct"] = round(float(m["pending_count"]) / total * 100, 2) if total > 0 else 0.0

        # Fraud metrics
        m["fraud_rate_pct"] = round(float(m["fraud_count"]) / total * 100, 2) if total > 0 else 0.0
        m["fraud_by_value_rate_pct"] = round(float(m["fraud_amount_total"]) / total_amt * 100, 2) if total_amt > 0 else 0.0
        m["clean_transaction_rate_pct"] = round(100.0 - m["fraud_rate_pct"], 2)
        m["recovery_opportunity_inr"] = round(float(m["failed_amount_total"]), 2)

        # Efficiency metrics
        m["effective_success_rate_pct"] = round(float(clean_success_count) / total * 100, 2) if total > 0 else 0.0
        m["problematic_rate_pct"] = round(float(problematic_count) / total * 100, 2) if total > 0 else 0.0

        value_at_risk = float(m["failed_amount_total"]) + float(m["fraud_amount_total"])
        m["value_at_risk_pct"] = round(value_at_risk / total_amt * 100, 2) if total_amt > 0 else 0.0

        m["operational_health_score"] = self._compute_operational_health_score(m)

        # Round all floats
        m = self._round_metrics(m)
        return m

    # ------------------------------------------------------------------
    # Internal: single-pass grouped metric computation
    # ------------------------------------------------------------------

    def _compute_metrics_grouped(self, df: pd.DataFrame, group_cols: List[str]) -> pd.DataFrame:
        """
        Compute the full metric catalog grouped by *group_cols* in a single
        ``groupby().agg()`` call.

        Args:
            df: The (filtered) DataFrame.
            group_cols: Column name(s) to group by.

        Returns:
            DataFrame with one row per group value and columns for every metric.
        """
        self._ensure_mask_columns(df)

        agg_dict = {
            "total_transactions": ("transaction_id", "count"),
            "total_amount_inr": ("amount_inr", "sum"),
            "avg_amount_inr": ("amount_inr", "mean"),
            "median_amount_inr": ("amount_inr", "median"),
            "min_amount_inr": ("amount_inr", "min"),
            "max_amount_inr": ("amount_inr", "max"),
            "amount_std_inr": ("amount_inr", "std"),
            "success_count": ("_is_success", "sum"),
            "failed_count": ("_is_failed", "sum"),
            "pending_count": ("_is_pending", "sum"),
            "fraud_count": ("_is_fraud", "sum"),
            "success_amount_total": ("_success_amount", "sum"),
            "failed_amount_total": ("_failed_amount", "sum"),
            "fraud_amount_total": ("_fraud_amount", "sum"),
            "clean_success_count": ("_clean_success", "sum"),
            "problematic_count": ("_is_problematic", "sum"),
        }

        g = df.groupby(group_cols, observed=True).agg(**agg_dict).reset_index()
        total_global = float(self.total_records)
        total_amt_global = float(self.df["amount_inr"].sum())

        # Derive rates
        t = g["total_transactions"].astype(float)
        ta = g["total_amount_inr"].astype(float)

        g["data_share_pct"] = (t / total_global * 100).round(2)
        g["amount_share_pct"] = (ta / total_amt_global * 100).round(2)
        g["wallet_concentration_ratio"] = np.where(g["data_share_pct"] > 0, (g["amount_share_pct"] / g["data_share_pct"]).round(4), 0.0)

        g["success_rate_pct"] = np.where(t > 0, (g["success_count"] / t * 100).round(2), 0.0)
        g["failure_rate_pct"] = np.where(t > 0, (g["failed_count"] / t * 100).round(2), 0.0)
        g["pending_rate_pct"] = np.where(t > 0, (g["pending_count"] / t * 100).round(2), 0.0)

        g["fraud_rate_pct"] = np.where(t > 0, (g["fraud_count"] / t * 100).round(2), 0.0)
        g["fraud_by_value_rate_pct"] = np.where(ta > 0, (g["fraud_amount_total"] / ta * 100).round(2), 0.0)
        g["clean_transaction_rate_pct"] = (100.0 - g["fraud_rate_pct"]).round(2)
        g["recovery_opportunity_inr"] = g["failed_amount_total"].round(2)

        g["effective_success_rate_pct"] = np.where(t > 0, (g["clean_success_count"] / t * 100).round(2), 0.0)
        g["problematic_rate_pct"] = np.where(t > 0, (g["problematic_count"] / t * 100).round(2), 0.0)

        g["value_at_risk_pct"] = np.where(ta > 0, ((g["failed_amount_total"] + g["fraud_amount_total"]) / ta * 100).round(2), 0.0)

        # Operational health score per group
        sr = g["success_rate_pct"] / 100.0
        fr = g["fraud_rate_pct"] / 100.0
        pr = g["pending_rate_pct"] / 100.0
        g["operational_health_score"] = ((sr * 0.5 + (1 - fr) * 0.3 + (1 - pr) * 0.2) * 100).round(2)

        # Drop internal columns
        g.drop(columns=["clean_success_count", "problematic_count"], inplace=True, errors="ignore")

        return g

    # ------------------------------------------------------------------
    # Internal: distribution metrics (ungrouped only)
    # ------------------------------------------------------------------

    def _compute_distribution_metrics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Compute distribution breakdowns for categorical columns.

        Only computed for ungrouped analysis modes.

        Args:
            df: Filtered DataFrame.

        Returns:
            Dict with distribution percentages for transaction_type, device, network,
            plus peak hour and peak day.
        """
        n = len(df)
        if n == 0:
            return {}

        dist: Dict[str, Any] = {}

        # Transaction type distribution
        if "transaction_type" in df.columns:
            vc = df["transaction_type"].value_counts(normalize=True) * 100
            dist["transaction_type_distribution"] = {str(k): round(v, 2) for k, v in vc.items()}

        # Device distribution
        if "device_type" in df.columns:
            vc = df["device_type"].value_counts(normalize=True) * 100
            dist["device_distribution"] = {str(k): round(v, 2) for k, v in vc.items()}

        # Network distribution
        if "network_type" in df.columns:
            vc = df["network_type"].value_counts(normalize=True) * 100
            dist["network_distribution"] = {str(k): round(v, 2) for k, v in vc.items()}

        # Peak hour & day
        if "hour_of_day" in df.columns:
            dist["peak_hour"] = int(df["hour_of_day"].mode().iloc[0]) if len(df) > 0 else None
        if "day_of_week" in df.columns:
            dist["peak_day"] = int(df["day_of_week"].mode().iloc[0]) if len(df) > 0 else None

        return dist

    # ------------------------------------------------------------------
    # Internal: global percentiles (cached)
    # ------------------------------------------------------------------

    def _compute_global_percentiles(self) -> Dict[str, Dict[str, float]]:
        """
        Pre-compute percentile distributions for key metrics across the full dataset.

        Returns:
            Nested dict keyed by metric name mapping to percentile values.
        """
        amt = self.df["amount_inr"].dropna()
        pctiles = [10, 25, 50, 75, 90, 95]

        amount_dist = {}
        if len(amt) > 0:
            for p in pctiles:
                amount_dist[f"p{p}"] = round(float(np.percentile(amt, p)), 2)

        # Failure rate and fraud rate by grouped segments (per-group distributions)
        # We approximate distributions by computing per-state rates
        group_col = "sender_state" if "sender_state" in self.df.columns else "sender_bank"
        g = self.df.groupby(group_col, observed=True).agg(
            _n=("transaction_id", "count"),
            _failed=("_is_failed", "sum"),
            _fraud=("_is_fraud", "sum"),
            _amt_mean=("amount_inr", "mean"),
        ).reset_index()
        g["failure_rate"] = np.where(g["_n"] > 0, g["_failed"] / g["_n"] * 100, 0)
        g["fraud_rate"] = np.where(g["_n"] > 0, g["_fraud"] / g["_n"] * 100, 0)

        failure_dist = {}
        fraud_dist = {}
        avg_amt_dist = {}
        for p in pctiles:
            failure_dist[f"p{p}"] = round(float(np.percentile(g["failure_rate"], p)), 4)
            fraud_dist[f"p{p}"] = round(float(np.percentile(g["fraud_rate"], p)), 4)
            avg_amt_dist[f"p{p}"] = round(float(np.percentile(g["_amt_mean"], p)), 2)

        return {
            "amount_inr": amount_dist,
            "failure_rate_pct": failure_dist,
            "fraud_rate_pct": fraud_dist,
            "avg_amount_inr": avg_amt_dist,
        }

    # ------------------------------------------------------------------
    # Internal: benchmark deltas
    # ------------------------------------------------------------------

    def _compute_benchmarks_delta(self, metrics: Dict[str, Any],
                                   benchmark: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Compute delta between segment metrics and benchmark (global by default).

        Args:
            metrics: Segment metrics dict.
            benchmark: Benchmark metrics dict; defaults to global_benchmarks.

        Returns:
            Tuple of (benchmarks_dict, deltas_dict).
        """
        bench = benchmark or self.global_benchmarks
        benchmarks_out: Dict[str, Any] = {}
        deltas_out: Dict[str, Any] = {}

        compare_keys = [
            "total_transactions", "avg_amount_inr", "median_amount_inr",
            "success_rate_pct", "failure_rate_pct", "pending_rate_pct",
            "fraud_rate_pct", "fraud_by_value_rate_pct", "effective_success_rate_pct",
            "problematic_rate_pct", "value_at_risk_pct", "operational_health_score",
            "total_amount_inr", "amount_std_inr", "p25_amount_inr", "p75_amount_inr",
            "p95_amount_inr", "wallet_concentration_ratio",
        ]

        for key in compare_keys:
            bv = bench.get(key)
            sv = metrics.get(key)
            if bv is not None and sv is not None:
                benchmarks_out[key] = self._to_num(bv)
                abs_delta = round(self._to_num(sv) - self._to_num(bv), 2)
                pct_delta = round(abs_delta / self._to_num(bv) * 100, 2) if self._to_num(bv) != 0 else 0.0
                deltas_out[key] = {
                    "absolute_delta": abs_delta,
                    "pct_delta": pct_delta,
                }

        return benchmarks_out, deltas_out

    # ------------------------------------------------------------------
    # Internal: confidence intervals (Wilson score)
    # ------------------------------------------------------------------

    def _compute_confidence_intervals(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute 95% Wilson score confidence intervals for all rate metrics.

        Args:
            metrics: Computed metrics dict.

        Returns:
            Dict of rate metric names to {lower_ci, upper_ci}.
        """
        ci: Dict[str, Any] = {}
        total = self._to_num(metrics.get("total_transactions", 0))
        if total == 0:
            return ci

        z = 1.96  # 95% CI

        rate_keys = {
            "success_rate_pct": "success_count",
            "failure_rate_pct": "failed_count",
            "pending_rate_pct": "pending_count",
            "fraud_rate_pct": "fraud_count",
            "effective_success_rate_pct": None,
            "problematic_rate_pct": None,
        }

        for rate_key, count_key in rate_keys.items():
            rate_val = self._to_num(metrics.get(rate_key, 0)) / 100.0
            if count_key:
                successes = self._to_num(metrics.get(count_key, 0))
            else:
                successes = rate_val * total

            lower, upper = self._wilson_interval(successes, total, z)
            ci[rate_key] = {
                "lower_ci": round(lower * 100, 4),
                "upper_ci": round(upper * 100, 4),
            }

        return ci

    @staticmethod
    def _wilson_interval(successes: float, n: float, z: float = 1.96) -> Tuple[float, float]:
        """
        Wilson score interval for a binomial proportion.

        Args:
            successes: Number of successes.
            n: Total trials.
            z: Z-score for confidence level (1.96 for 95%).

        Returns:
            Tuple of (lower_bound, upper_bound) as proportions.
        """
        if n == 0:
            return 0.0, 0.0
        p = successes / n
        denom = 1 + z * z / n
        centre = p + z * z / (2 * n)
        spread = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
        lower = max(0.0, (centre - spread) / denom)
        upper = min(1.0, (centre + spread) / denom)
        return lower, upper

    # ------------------------------------------------------------------
    # Internal: operational health score
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_operational_health_score(metrics: Dict[str, Any]) -> float:
        """
        Compute composite operational health score (0-100).

        Formula: (success_rate × 0.5) + ((1 − fraud_rate) × 0.3) + ((1 − pending_rate) × 0.2)
        Each component normalised to 0-1.

        Args:
            metrics: Dict containing success_rate_pct, fraud_rate_pct, pending_rate_pct.

        Returns:
            Float 0-100.
        """
        sr = float(metrics.get("success_rate_pct", 0)) / 100.0
        fr = float(metrics.get("fraud_rate_pct", 0)) / 100.0
        pr = float(metrics.get("pending_rate_pct", 0)) / 100.0
        score = (sr * 0.5 + (1 - fr) * 0.3 + (1 - pr) * 0.2) * 100
        return round(score, 2)

    # ------------------------------------------------------------------
    # Internal: health grade
    # ------------------------------------------------------------------

    @staticmethod
    def _assign_health_grade(score: float) -> str:
        """
        Assign letter grade from operational health score.

        Args:
            score: 0-100 health score.

        Returns:
            Letter grade string.
        """
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"

    # ------------------------------------------------------------------
    # Internal: anomaly detection
    # ------------------------------------------------------------------

    def _detect_anomalies(self, metrics: Dict[str, Any],
                          threshold_multiplier: float = 1.5) -> Dict[str, Any]:
        """
        Flag metrics that deviate significantly from global benchmarks.

        For negative metrics (failure_rate, fraud_rate, etc.), flag if value exceeds
        threshold_multiplier × global average.
        For positive metrics (success_rate, etc.), flag if value falls below
        (1 / threshold_multiplier) × global average.

        Args:
            metrics: Computed segment metrics.
            threshold_multiplier: Deviation multiple to trigger flag.

        Returns:
            Dict with anomaly_report list and anomaly_severity.
        """
        bench = self.global_benchmarks

        negative_metrics = [
            "failure_rate_pct", "pending_rate_pct", "fraud_rate_pct",
            "fraud_by_value_rate_pct", "problematic_rate_pct", "value_at_risk_pct",
        ]
        positive_metrics = [
            "success_rate_pct", "effective_success_rate_pct",
            "clean_transaction_rate_pct", "operational_health_score",
        ]
        neutral_metrics = [
            "avg_amount_inr", "median_amount_inr", "total_transactions",
        ]

        anomalies: List[Dict[str, Any]] = []

        for key in negative_metrics:
            seg_val = self._to_num(metrics.get(key, 0))
            global_val = self._to_num(bench.get(key, 0))
            if global_val > 0:
                z_score = round((seg_val - global_val) / max(global_val * 0.5, 0.001), 2)
                if seg_val > global_val * threshold_multiplier:
                    anomalies.append({
                        "metric": key,
                        "segment_value": seg_val,
                        "global_average": global_val,
                        "z_score": z_score,
                        "direction": "Above Normal",
                        "anomaly_statement": f"{key} is {seg_val}% vs global average of {global_val}%, which is {round(seg_val / global_val, 2)}x the baseline."
                    })

        for key in positive_metrics:
            seg_val = self._to_num(metrics.get(key, 0))
            global_val = self._to_num(bench.get(key, 0))
            if global_val > 0:
                z_score = round((seg_val - global_val) / max(global_val * 0.5, 0.001), 2)
                if seg_val < global_val / threshold_multiplier:
                    anomalies.append({
                        "metric": key,
                        "segment_value": seg_val,
                        "global_average": global_val,
                        "z_score": z_score,
                        "direction": "Below Normal",
                        "anomaly_statement": f"{key} is {seg_val}% vs global average of {global_val}%, which is only {round(seg_val / global_val, 2)}x the baseline."
                    })

        count = len(anomalies)
        if count == 0:
            severity = "Normal"
        elif count <= 2:
            severity = "Mild Anomaly"
        elif count <= 4:
            severity = "Moderate Anomaly"
        else:
            severity = "Severe Anomaly"

        return {
            "anomaly_report": anomalies,
            "anomaly_severity": severity,
            "anomalies_flagged": count,
        }

    # ------------------------------------------------------------------
    # Internal: executive summary
    # ------------------------------------------------------------------

    def _build_executive_summary(self, metrics: Dict[str, Any],
                                  deltas: Dict[str, Any],
                                  segment_label: str = "the analyzed segment") -> Dict[str, Any]:
        """
        Build a complete executive summary with specific numbers.

        The summary block contains key_finding, health_grade, top_concern,
        top_strength, risk_flags, and a multi-sentence executive_summary narrative.

        Args:
            metrics: Computed metrics dict.
            deltas: Delta-from-benchmark dict.
            segment_label: Human-readable description of the segment.

        Returns:
            Summary dict.
        """
        health_score = self._to_num(metrics.get("operational_health_score", 0))
        grade = self._assign_health_grade(health_score)

        # Find top strength (biggest positive delta on positive metrics)
        positive_keys = ["success_rate_pct", "effective_success_rate_pct", "avg_amount_inr", "operational_health_score"]
        negative_keys = ["failure_rate_pct", "fraud_rate_pct", "pending_rate_pct", "value_at_risk_pct", "problematic_rate_pct"]

        best_strength = None
        best_strength_delta = -float("inf")
        for k in positive_keys:
            d = deltas.get(k, {})
            pd_val = d.get("pct_delta", 0)
            if pd_val > best_strength_delta:
                best_strength_delta = pd_val
                best_strength = k

        best_concern = None
        best_concern_delta = -float("inf")
        for k in negative_keys:
            d = deltas.get(k, {})
            pd_val = d.get("pct_delta", 0)
            if pd_val > best_concern_delta:
                best_concern_delta = pd_val
                best_concern = k

        # Risk flags
        risk_flags: List[str] = []
        for k in negative_keys:
            d = deltas.get(k, {})
            if d.get("pct_delta", 0) > 50:
                risk_flags.append(k)

        # Build executive summary paragraph
        success_rate = metrics.get("success_rate_pct", 0)
        failure_rate = metrics.get("failure_rate_pct", 0)
        fraud_rate = metrics.get("fraud_rate_pct", 0)
        var_pct = metrics.get("value_at_risk_pct", 0)
        total_txn = metrics.get("total_transactions", 0)
        avg_amt = metrics.get("avg_amount_inr", 0)

        global_failure = self.global_benchmarks.get("failure_rate_pct", 0)
        global_fraud = self.global_benchmarks.get("fraud_rate_pct", 0)
        global_success = self.global_benchmarks.get("success_rate_pct", 0)

        # Sentence 1: What was analyzed + grade
        s1 = f"Analysis of {segment_label} ({total_txn:,} transactions) yields an operational health grade of {grade} ({health_score}/100)."

        # Sentence 2: Strongest positive
        if best_strength and best_strength in metrics:
            s2_val = metrics[best_strength]
            s2 = f"The strongest metric is {best_strength.replace('_', ' ')} at {s2_val}%." if "pct" in best_strength else f"The strongest metric is {best_strength.replace('_', ' ')} at {s2_val}."
        else:
            s2 = f"Success rate stands at {success_rate}%."

        # Sentence 3: Most concerning + comparison
        if best_concern and best_concern in metrics:
            s3_val = metrics[best_concern]
            s3_bench = self.global_benchmarks.get(best_concern, 0)
            s3 = f"The primary concern is {best_concern.replace('_', ' ')} at {s3_val}% compared to the global average of {s3_bench}%."
        else:
            s3 = f"Failure rate is {failure_rate}% vs the platform average of {global_failure}%."

        # Sentence 4: Actionable implication
        if float(failure_rate) > float(global_failure) * 1.2:
            s4 = f"With {var_pct}% of transaction value at risk, targeted reliability improvements could recover ₹{metrics.get('recovery_opportunity_inr', 0):,.0f} in failed transaction value."
        elif float(fraud_rate) > float(global_fraud) * 1.5:
            s4 = f"The elevated fraud rate of {fraud_rate}% warrants enhanced monitoring and verification protocols for this segment."
        else:
            s4 = f"This segment operates within healthy parameters; maintaining current service levels while monitoring for seasonal variations is recommended."

        exec_summary = f"{s1} {s2} {s3} {s4}"

        # Key finding: single most important number
        key_finding = f"{segment_label} has a {grade}-grade health score of {health_score}/100 with {success_rate}% success rate, {failure_rate}% failure rate, and {var_pct}% of value at risk."

        return {
            "key_finding": key_finding,
            "operational_health_score": health_score,
            "health_grade": grade,
            "top_concern": best_concern,
            "top_strength": best_strength,
            "risk_flags": risk_flags,
            "executive_summary": exec_summary,
        }

    # ------------------------------------------------------------------
    # Internal: funnel stages
    # ------------------------------------------------------------------

    def _compute_funnel_stages(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Compute transaction funnel: Initiated → Processed → Succeeded → Clean Success.

        Args:
            df: Filtered DataFrame.

        Returns:
            Dict with stages, drop-off rates, value funnel, and primary leak stage.
        """
        self._ensure_mask_columns(df)
        n = len(df)
        if n == 0:
            return {"stages": [], "overall_funnel_efficiency": 0.0}

        # Compute all counts in one pass via Series operations
        initiated = n
        pending_count = int(df["_is_pending"].sum())
        processed = initiated - pending_count
        succeeded = int(df["_is_success"].sum())
        clean_success = int(df["_clean_success"].sum())

        # Value funnel
        total_value = float(df["amount_inr"].sum())
        processed_value = total_value - float(df["amount_inr"].where(df["_is_pending"], 0).sum())
        success_value = float(df["_success_amount"].sum())
        clean_value = float(df["amount_inr"].where(df["_clean_success"], 0).sum())

        stages = [
            {"stage": "Initiated", "count": initiated, "value_inr": round(total_value, 2)},
            {"stage": "Processed", "count": processed, "value_inr": round(processed_value, 2)},
            {"stage": "Succeeded", "count": succeeded, "value_inr": round(success_value, 2)},
            {"stage": "Clean Success", "count": clean_success, "value_inr": round(clean_value, 2)},
        ]

        # Drop-offs between consecutive stages
        drops = []
        stage_counts = [initiated, processed, succeeded, clean_success]
        stage_names = ["Initiated→Processed", "Processed→Succeeded", "Succeeded→Clean Success"]
        max_drop_rate = 0.0
        primary_leak = stage_names[0]

        for i in range(len(stage_counts) - 1):
            prev = stage_counts[i]
            curr = stage_counts[i + 1]
            drop_count = prev - curr
            drop_rate = round(drop_count / prev * 100, 2) if prev > 0 else 0.0
            conversion = round(curr / prev * 100, 2) if prev > 0 else 0.0
            drops.append({
                "transition": stage_names[i],
                "drop_off_count": drop_count,
                "drop_off_rate_pct": drop_rate,
                "conversion_rate_pct": conversion,
            })
            if drop_rate > max_drop_rate:
                max_drop_rate = drop_rate
                primary_leak = stage_names[i]

        overall_efficiency = round(clean_success / initiated * 100, 2) if initiated > 0 else 0.0
        value_leak = round((total_value - clean_value) / total_value * 100, 2) if total_value > 0 else 0.0

        return {
            "stages": stages,
            "drop_offs": drops,
            "overall_funnel_efficiency": overall_efficiency,
            "primary_leak_stage": primary_leak,
            "value_funnel": {
                "total_value_inr": round(total_value, 2),
                "clean_success_value_inr": round(clean_value, 2),
                "value_leak_pct": value_leak,
            },
        }

    # ------------------------------------------------------------------
    # Internal: percentile context for a metric
    # ------------------------------------------------------------------

    def _percentile_rank(self, metric_key: str, value: float) -> Optional[str]:
        """
        Determine percentile status label for a metric value.

        Args:
            metric_key: Key into global_percentiles.
            value: The segment's metric value.

        Returns:
            Status label string or None if metric not in cache.
        """
        dist = self.global_percentiles.get(metric_key)
        if not dist:
            return None

        p90 = dist.get("p90", dist.get("p95", float("inf")))
        p75 = dist.get("p75", float("inf"))
        p25 = dist.get("p25", 0)
        p10 = dist.get("p10", 0)

        if value >= p90:
            return "Excellent"
        elif value >= p75:
            return "Good"
        elif value >= p25:
            return "Average"
        elif value >= p10:
            return "Below Average"
        else:
            return "Poor"

    def _percentile_rank_inverted(self, metric_key: str, value: float) -> Optional[str]:
        """
        Percentile status label for an inverted metric (lower is better).

        Args:
            metric_key: Key into global_percentiles.
            value: The segment's metric value.

        Returns:
            Status label string or None.
        """
        dist = self.global_percentiles.get(metric_key)
        if not dist:
            return None

        p10 = dist.get("p10", 0)
        p25 = dist.get("p25", 0)
        p75 = dist.get("p75", float("inf"))
        p90 = dist.get("p90", dist.get("p95", float("inf")))

        if value <= p10:
            return "Excellent"
        elif value <= p25:
            return "Good"
        elif value <= p75:
            return "Average"
        elif value <= p90:
            return "Below Average"
        else:
            return "Poor"

    # ------------------------------------------------------------------
    # Internal: null counts
    # ------------------------------------------------------------------

    @staticmethod
    def _null_counts(df: pd.DataFrame) -> Dict[str, int]:
        """
        Count null values per key column.

        Args:
            df: DataFrame to inspect.

        Returns:
            Dict of column → null count for columns that have at least 1 null.
        """
        key_cols = [
            "transaction_id", "timestamp", "transaction_status", "transaction_type",
            "merchant_category", "amount_inr", "device_type", "network_type",
            "sender_bank", "receiver_bank", "sender_age_group", "fraud_flag",
        ]
        result = {}
        for c in key_cols:
            if c in df.columns:
                nc = int(df[c].isna().sum())
                if nc > 0:
                    result[c] = nc
        return result

    # ------------------------------------------------------------------
    # Internal: empty metrics
    # ------------------------------------------------------------------

    @staticmethod
    def _empty_metrics() -> Dict[str, Any]:
        """Return a zeroed-out metric dict for empty DataFrames."""
        return {
            "total_transactions": 0, "transactions_per_day": 0, "transactions_per_hour": 0,
            "data_share_pct": 0.0, "total_amount_inr": 0.0, "avg_amount_inr": 0.0,
            "median_amount_inr": 0.0, "min_amount_inr": 0.0, "max_amount_inr": 0.0,
            "amount_std_inr": 0.0, "p25_amount_inr": 0.0, "p75_amount_inr": 0.0,
            "p95_amount_inr": 0.0, "amount_share_pct": 0.0, "wallet_concentration_ratio": 0.0,
            "success_count": 0, "success_rate_pct": 0.0, "failed_count": 0,
            "failure_rate_pct": 0.0, "pending_count": 0, "pending_rate_pct": 0.0,
            "success_amount_total": 0.0, "failed_amount_total": 0.0,
            "recovery_opportunity_inr": 0.0, "fraud_count": 0, "fraud_rate_pct": 0.0,
            "fraud_amount_total": 0.0, "fraud_by_value_rate_pct": 0.0,
            "clean_transaction_rate_pct": 0.0, "effective_success_rate_pct": 0.0,
            "problematic_rate_pct": 0.0, "value_at_risk_pct": 0.0,
            "operational_health_score": 0.0,
        }

    # ------------------------------------------------------------------
    # Internal: helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_num(val: Any) -> float:
        """Safely convert a value to float."""
        try:
            return float(val)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _round_metrics(m: Dict[str, Any]) -> Dict[str, Any]:
        """Round all float values in a metrics dict to 2 decimal places."""
        out = {}
        for k, v in m.items():
            if isinstance(v, float):
                out[k] = round(v, 2)
            elif isinstance(v, (np.floating, np.float64)):
                out[k] = round(float(v), 2)
            elif isinstance(v, (np.integer, np.int64)):
                out[k] = int(v)
            else:
                out[k] = v
        return out

    def _filter_metrics(self, metrics: Dict[str, Any],
                        include: Optional[List[str]] = None,
                        exclude: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Filter the metrics dict based on include/exclude lists.

        Args:
            metrics: Full metrics dict.
            include: If provided, only keep these keys.
            exclude: If provided, remove these keys.

        Returns:
            Filtered metrics dict.
        """
        if include:
            metrics = {k: v for k, v in metrics.items() if k in include}
        if exclude:
            metrics = {k: v for k, v in metrics.items() if k not in exclude}
        return metrics

    def _base_output(self, analysis_mode: str, df_filtered: pd.DataFrame,
                     metrics: Dict[str, Any], params: Dict[str, Any],
                     mode_specific: Dict[str, Any],
                     segment_label: str = "the analyzed segment") -> str:
        """
        Build the standard output wrapper shared by all analysis modes.

        Args:
            analysis_mode: The mode that was run.
            df_filtered: The filtered DataFrame.
            metrics: Computed metrics dict.
            params: Original parameters dict.
            mode_specific: Mode-specific output dict.
            segment_label: Human-readable segment description.

        Returns:
            JSON string with the full response.
        """
        include_benchmarks = params.get("include_benchmarks", True)
        include_ci = params.get("include_confidence_intervals", True)
        include_pctx = params.get("include_percentile_context", True)

        benchmarks_out: Dict[str, Any] = {}
        deltas_out: Dict[str, Any] = {}
        ci_out: Dict[str, Any] = {}

        if include_benchmarks:
            benchmark_data = None
            if params.get("benchmark_filters"):
                bench_df = self._apply_filters(self.df, params["benchmark_filters"])
                benchmark_data = self._compute_metrics_single_pass(bench_df)
            benchmarks_out, deltas_out = self._compute_benchmarks_delta(metrics, benchmark_data)

        if include_ci:
            ci_out = self._compute_confidence_intervals(metrics)

        # Percentile context
        if include_pctx:
            for key in ["avg_amount_inr", "failure_rate_pct", "fraud_rate_pct"]:
                val = self._to_num(metrics.get(key, 0))
                if key in ("failure_rate_pct", "fraud_rate_pct"):
                    label = self._percentile_rank_inverted(key, val)
                else:
                    label = self._percentile_rank(key, val)
                if label and key in deltas_out:
                    deltas_out[key]["percentile_rank"] = label
                    deltas_out[key]["status_label"] = label

        # Apply include/exclude filters on metric keys
        filtered_metrics = self._filter_metrics(
            metrics,
            include=params.get("metrics_to_include"),
            exclude=params.get("metrics_to_exclude"),
        )

        summary = self._build_executive_summary(metrics, deltas_out, segment_label)

        output = {
            "success": True,
            "analysis_mode": analysis_mode,
            "filters_applied": params.get("filters", []),
            "total_records_analyzed": int(metrics.get("total_transactions", len(df_filtered))),
            "data_share_of_full_dataset_pct": metrics.get("data_share_pct", 0),
            "metrics": filtered_metrics,
            "benchmarks": benchmarks_out,
            "deltas": deltas_out,
            "confidence_intervals": ci_out,
            "mode_specific_output": mode_specific,
            "summary": summary,
            "metadata": {
                "computation_mode": "single_pass_vectorized",
                "benchmark_source": "cached_global_averages",
                "execution_note": "",
                "null_counts": self._null_counts(df_filtered),
            },
        }

        return json.dumps(output, default=str)

    def _error_response(self, mode: str, error: str, suggestion: str) -> str:
        """
        Build a standard error response.

        Args:
            mode: The analysis mode attempted.
            error: Error message.
            suggestion: What the caller should try instead.

        Returns:
            JSON string with error info.
        """
        return json.dumps({
            "success": False,
            "analysis_mode": mode,
            "error": error,
            "suggestion": suggestion,
        })

    def _build_segment_label(self, filters: List[Dict[str, Any]]) -> str:
        """
        Build a human-readable segment label from filter conditions.

        Args:
            filters: List of filter dicts.

        Returns:
            Descriptive string.
        """
        if not filters:
            return "the full dataset"
        parts = []
        for f in filters:
            col = f.get("column", "")
            op = f.get("operator", "==")
            val = f.get("value", "")
            if op == "==":
                parts.append(f"{val} {col.replace('_', ' ')}")
            elif op == ">":
                parts.append(f"{col.replace('_', ' ')} > {val}")
            elif op == "<":
                parts.append(f"{col.replace('_', ' ')} < {val}")
            elif op == ">=":
                parts.append(f"{col.replace('_', ' ')} >= {val}")
            elif op == "<=":
                parts.append(f"{col.replace('_', ' ')} <= {val}")
            elif op == "in":
                parts.append(f"{col.replace('_', ' ')} in {val}")
            else:
                parts.append(f"{col} {op} {val}")
        return " & ".join(parts) if parts else "the analyzed segment"

    # ==================================================================
    # Analysis Modes
    # ==================================================================

    # ------------------------------------------------------------------
    # 1. snapshot
    # ------------------------------------------------------------------

    def _mode_snapshot(self, params: Dict[str, Any]) -> str:
        """
        Full KPI snapshot of a filtered dataset — no grouping.

        Args:
            params: Parameters dict with optional filters.

        Returns:
            JSON string with complete snapshot.
        """
        filters = params.get("filters", [])
        df = self._apply_filters(self.df, filters)

        if len(df) == 0:
            return self._error_response("snapshot", "No records match the given filters.",
                                        "Broaden filter conditions or check column/value spelling.")

        metrics = self._compute_metrics_single_pass(df)
        distributions = self._compute_distribution_metrics(df)
        mode_specific = {"distributions": distributions}

        label = self._build_segment_label(filters)
        return self._base_output("snapshot", df, metrics, params, mode_specific, label)

    # ------------------------------------------------------------------
    # 2. grouped_snapshot
    # ------------------------------------------------------------------

    def _mode_grouped_snapshot(self, params: Dict[str, Any]) -> str:
        """
        Full KPI snapshot grouped by one dimension column.

        Args:
            params: Parameters dict with group_by (string) and optional filters.

        Returns:
            JSON string with per-group metrics.
        """
        filters = params.get("filters", [])
        group_by = params.get("group_by")
        if not group_by:
            return self._error_response("grouped_snapshot", "group_by is required.",
                                        "Provide a column name in group_by.")

        if isinstance(group_by, list):
            group_by = group_by[0]

        group_by = data_loader.resolve_column(group_by)

        df = self._apply_filters(self.df, filters)
        if len(df) == 0:
            return self._error_response("grouped_snapshot",
                                        "No records match the given filters.",
                                        "Broaden filter conditions.")

        g = self._compute_metrics_grouped(df, [group_by])

        # Rank by health score
        g = g.sort_values("operational_health_score", ascending=False).reset_index(drop=True)
        g["rank_by_health_score"] = range(1, len(g) + 1)

        # vs group average
        numeric_cols = g.select_dtypes(include=[np.number]).columns.tolist()
        group_avg = {c: round(float(g[c].mean()), 2) for c in numeric_cols if c != "rank_by_health_score"}

        groups_data = []
        for _, row in g.iterrows():
            rd = row.to_dict()
            vs_avg = {}
            for c in numeric_cols:
                if c in group_avg and group_avg[c] != 0:
                    vs_avg[c] = round(float(rd.get(c, 0)) - group_avg[c], 2)
            rd["vs_group_average"] = vs_avg
            groups_data.append(self._round_metrics(rd))

        # Group summary: leader and laggard per key metric
        key_metrics = ["success_rate_pct", "failure_rate_pct", "fraud_rate_pct",
                       "avg_amount_inr", "operational_health_score", "total_transactions"]
        group_summary: Dict[str, Any] = {}
        for km in key_metrics:
            if km in g.columns:
                if km in ("failure_rate_pct", "fraud_rate_pct"):
                    leader_idx = g[km].idxmin()
                    laggard_idx = g[km].idxmax()
                else:
                    leader_idx = g[km].idxmax()
                    laggard_idx = g[km].idxmin()
                group_summary[km] = {
                    "leader": str(g.loc[leader_idx, group_by]),
                    "leader_value": round(float(g.loc[leader_idx, km]), 2),
                    "laggard": str(g.loc[laggard_idx, group_by]),
                    "laggard_value": round(float(g.loc[laggard_idx, km]), 2),
                }

        # Compute overall metrics for summary
        overall_metrics = self._compute_metrics_single_pass(df)
        label = self._build_segment_label(filters) + f" grouped by {group_by}"

        mode_specific = {
            "groups": groups_data,
            "group_averages": group_avg,
            "group_summary": group_summary,
            "group_by_column": group_by,
            "group_count": len(groups_data),
        }

        return self._base_output("grouped_snapshot", df, overall_metrics, params, mode_specific, label)

    # ------------------------------------------------------------------
    # 3. multi_group_snapshot
    # ------------------------------------------------------------------

    def _mode_multi_group_snapshot(self, params: Dict[str, Any]) -> str:
        """
        Full KPI snapshot grouped by two dimensions simultaneously.

        Args:
            params: Parameters dict with group_by (list of 2 strings) and optional filters.

        Returns:
            JSON string with per-combination metrics plus marginals.
        """
        filters = params.get("filters", [])
        group_by = params.get("group_by", [])
        if not isinstance(group_by, list) or len(group_by) < 2:
            return self._error_response("multi_group_snapshot",
                                        "group_by must be a list of exactly 2 column names.",
                                        "Provide e.g. [\"device_type\", \"network_type\"].")

        dim1, dim2 = data_loader.resolve_column(group_by[0]), data_loader.resolve_column(group_by[1])
        df = self._apply_filters(self.df, filters)
        if len(df) == 0:
            return self._error_response("multi_group_snapshot",
                                        "No records match the given filters.",
                                        "Broaden filter conditions.")

        g = self._compute_metrics_grouped(df, [dim1, dim2])
        g["combination_label"] = g[dim1].astype(str) + " + " + g[dim2].astype(str)

        # Best / worst by health score
        best_idx = g["operational_health_score"].idxmax()
        worst_idx = g["operational_health_score"].idxmin()

        # Marginals
        m1 = self._compute_metrics_grouped(df, [dim1])
        m2 = self._compute_metrics_grouped(df, [dim2])

        # Overall metrics
        overall_metrics = self._compute_metrics_single_pass(df)
        label = self._build_segment_label(filters) + f" grouped by {dim1} × {dim2}"

        combinations = []
        for _, row in g.iterrows():
            combinations.append(self._round_metrics(row.to_dict()))

        mode_specific = {
            "combinations": combinations,
            "best_combination": {
                "label": str(g.loc[best_idx, "combination_label"]),
                "health_score": round(float(g.loc[best_idx, "operational_health_score"]), 2),
            },
            "worst_combination": {
                "label": str(g.loc[worst_idx, "combination_label"]),
                "health_score": round(float(g.loc[worst_idx, "operational_health_score"]), 2),
            },
            "dimension_1_marginal": [self._round_metrics(r.to_dict()) for _, r in m1.iterrows()],
            "dimension_2_marginal": [self._round_metrics(r.to_dict()) for _, r in m2.iterrows()],
            "dimensions": [dim1, dim2],
            "combination_count": len(combinations),
        }

        return self._base_output("multi_group_snapshot", df, overall_metrics, params, mode_specific, label)

    # ------------------------------------------------------------------
    # 4. segment_profile
    # ------------------------------------------------------------------

    def _mode_segment_profile(self, params: Dict[str, Any]) -> str:
        """
        Deep single-segment diagnostic with benchmarking and status labels.

        Args:
            params: Parameters dict with filters defining the segment.

        Returns:
            JSON string with profiled segment, strengths, weaknesses, assessment.
        """
        filters = params.get("filters", [])
        df = self._apply_filters(self.df, filters)
        if len(df) == 0:
            return self._error_response("segment_profile",
                                        "No records match the given filters.",
                                        "Broaden filter conditions.")

        metrics = self._compute_metrics_single_pass(df)
        distributions = self._compute_distribution_metrics(df)

        # Status labels for each metric
        positive_metrics_keys = {
            "avg_amount_inr": "avg_amount_inr",
            "success_rate_pct": None,
            "effective_success_rate_pct": None,
            "operational_health_score": None,
        }
        negative_metrics_keys = {
            "failure_rate_pct": "failure_rate_pct",
            "fraud_rate_pct": "fraud_rate_pct",
        }

        metric_profiles: Dict[str, Any] = {}
        strengths: List[str] = []
        weaknesses: List[str] = []

        for key, pctile_key in positive_metrics_keys.items():
            val = self._to_num(metrics.get(key, 0))
            gl = self._to_num(self.global_benchmarks.get(key, 0))
            delta = round(val - gl, 2)
            if pctile_key:
                status = self._percentile_rank(pctile_key, val) or "Average"
            else:
                # Approximate based on delta
                pct_delta = (delta / gl * 100) if gl != 0 else 0
                if pct_delta > 10:
                    status = "Excellent"
                elif pct_delta > 2:
                    status = "Good"
                elif pct_delta > -5:
                    status = "Average"
                elif pct_delta > -15:
                    status = "Below Average"
                else:
                    status = "Poor"

            metric_profiles[key] = {
                "value": val, "global_average": gl, "delta": delta, "status": status
            }
            if status in ("Excellent", "Good"):
                strengths.append(key)
            elif status in ("Below Average", "Poor"):
                weaknesses.append(key)

        for key, pctile_key in negative_metrics_keys.items():
            val = self._to_num(metrics.get(key, 0))
            gl = self._to_num(self.global_benchmarks.get(key, 0))
            delta = round(val - gl, 2)
            if pctile_key:
                status = self._percentile_rank_inverted(pctile_key, val) or "Average"
            else:
                status = "Average"

            metric_profiles[key] = {
                "value": val, "global_average": gl, "delta": delta, "status": status
            }
            if status in ("Excellent", "Good"):
                strengths.append(key)
            elif status in ("Below Average", "Poor"):
                weaknesses.append(key)

        # Overall assessment paragraph
        label = self._build_segment_label(filters)
        health_score = metrics.get("operational_health_score", 0)
        grade = self._assign_health_grade(health_score)
        strengths_text = ", ".join(s.replace("_", " ") for s in strengths) if strengths else "none identified"
        weaknesses_text = ", ".join(w.replace("_", " ") for w in weaknesses) if weaknesses else "none identified"
        overall_assessment = (
            f"{label} scores a health grade of {grade} ({health_score}/100). "
            f"Key strengths: {strengths_text}. "
            f"Areas for improvement: {weaknesses_text}. "
            f"The segment represents {metrics.get('data_share_pct', 0)}% of total volume "
            f"and {metrics.get('amount_share_pct', 0)}% of total transaction value."
        )

        mode_specific = {
            "metric_profiles": metric_profiles,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "overall_assessment": overall_assessment,
            "distributions": distributions,
        }

        return self._base_output("segment_profile", df, metrics, params, mode_specific, label)

    # ------------------------------------------------------------------
    # 5. health_scorecard
    # ------------------------------------------------------------------

    def _mode_health_scorecard(self, params: Dict[str, Any]) -> str:
        """
        Structured health check producing sub-scores, letter grade, and risk flags.

        Args:
            params: Parameters dict with optional filters.

        Returns:
            JSON string with health scorecard.
        """
        filters = params.get("filters", [])
        threshold = params.get("flag_threshold_multiplier", 1.5)
        df = self._apply_filters(self.df, filters)
        if len(df) == 0:
            return self._error_response("health_scorecard",
                                        "No records match the given filters.",
                                        "Broaden filter conditions.")

        metrics = self._compute_metrics_single_pass(df)
        distributions = self._compute_distribution_metrics(df)

        gb = self.global_benchmarks

        # Sub-scores (each 0-100)
        success_rate = self._to_num(metrics.get("success_rate_pct", 0))
        fraud_rate = self._to_num(metrics.get("fraud_rate_pct", 0))
        pending_rate = self._to_num(metrics.get("pending_rate_pct", 0))
        effective_sr = self._to_num(metrics.get("effective_success_rate_pct", 0))
        data_share = self._to_num(metrics.get("data_share_pct", 0))
        wcr = self._to_num(metrics.get("wallet_concentration_ratio", 0))
        avg_amt = self._to_num(metrics.get("avg_amount_inr", 0))
        gb_avg_amt = self._to_num(gb.get("avg_amount_inr", 1))

        reliability_score = round(min(success_rate, 100.0), 2)
        fraud_score = round(max(0, min((1 - fraud_rate / 100) * 100, 100.0)), 2)

        # Volume score: how close data_share is to expected uniform share
        expected_share = 100.0 / max(self.df["sender_bank"].nunique(), 1)  # rough expected
        volume_ratio = data_share / expected_share if expected_share > 0 else 1
        volume_score = round(min(volume_ratio * 100, 100.0), 2)

        # Value score: based on wallet_concentration_ratio and avg_amount vs global
        amt_ratio = avg_amt / gb_avg_amt if gb_avg_amt > 0 else 1
        value_score = round(min(((wcr + amt_ratio) / 2) * 100, 100.0), 2)
        value_score = min(value_score, 100.0)

        # Efficiency score
        efficiency_score = round(min(effective_sr + (100 - pending_rate), 100.0) / 2 * 100 / 50, 2)
        efficiency_score = round(min(max((effective_sr * 0.7 + (100 - pending_rate) * 0.3), 0), 100), 2)

        overall_health = round(
            reliability_score * 0.35 + fraud_score * 0.25 +
            volume_score * 0.15 + value_score * 0.15 + efficiency_score * 0.10,
            2
        )
        overall_health = min(overall_health, 100.0)
        grade = self._assign_health_grade(overall_health)

        # Risk flags
        risk_flags: List[Dict[str, Any]] = []
        negative_check = {
            "failure_rate_pct": "Failure rate",
            "fraud_rate_pct": "Fraud rate",
            "pending_rate_pct": "Pending rate",
            "value_at_risk_pct": "Value at risk",
            "problematic_rate_pct": "Problematic rate",
        }
        for metric_key, label in negative_check.items():
            seg_val = self._to_num(metrics.get(metric_key, 0))
            gl_val = self._to_num(gb.get(metric_key, 0))
            if gl_val > 0 and seg_val > gl_val * threshold:
                risk_flags.append({
                    "metric": metric_key,
                    "label": label,
                    "segment_value": seg_val,
                    "global_average": gl_val,
                    "multiple": round(seg_val / gl_val, 2),
                })

        # Improvement priorities: top 3 metrics with largest negative deviation
        deviations = []
        compare_keys = ["success_rate_pct", "failure_rate_pct", "fraud_rate_pct",
                        "pending_rate_pct", "effective_success_rate_pct", "value_at_risk_pct"]
        for k in compare_keys:
            sv = self._to_num(metrics.get(k, 0))
            gv = self._to_num(gb.get(k, 0))
            if k in ("failure_rate_pct", "fraud_rate_pct", "pending_rate_pct", "value_at_risk_pct"):
                deviation = sv - gv  # higher is worse
            else:
                deviation = gv - sv  # lower is worse
            deviations.append({"metric": k, "deviation": round(deviation, 2)})
        deviations.sort(key=lambda x: x["deviation"], reverse=True)
        improvement_priorities = deviations[:3]

        label = self._build_segment_label(filters)
        mode_specific = {
            "sub_scores": {
                "reliability_score": reliability_score,
                "fraud_score": fraud_score,
                "volume_score": volume_score,
                "value_score": value_score,
                "efficiency_score": efficiency_score,
            },
            "overall_health_score": overall_health,
            "health_grade": grade,
            "risk_flags": risk_flags,
            "improvement_priorities": improvement_priorities,
            "distributions": distributions,
        }

        return self._base_output("health_scorecard", df, metrics, params, mode_specific, label)

    # ------------------------------------------------------------------
    # 6. transaction_type_profile
    # ------------------------------------------------------------------

    def _mode_transaction_type_profile(self, params: Dict[str, Any]) -> str:
        """
        Breakdown across all four transaction types in one pass.

        Args:
            params: Parameters dict with optional filters.

        Returns:
            JSON string with per-type metrics and cross-type comparisons.
        """
        filters = params.get("filters", [])
        df = self._apply_filters(self.df, filters)
        if len(df) == 0:
            return self._error_response("transaction_type_profile",
                                        "No records match the given filters.",
                                        "Broaden filter conditions.")

        g = self._compute_metrics_grouped(df, ["transaction_type"])

        total_filtered = float(len(df))
        total_amt_filtered = float(df["amount_inr"].sum())

        g["type_share_of_filtered_volume"] = (g["total_transactions"] / total_filtered * 100).round(2)
        g["type_share_of_total_amount"] = (g["total_amount_inr"] / total_amt_filtered * 100).round(2) if total_amt_filtered > 0 else 0.0

        types_data = []
        for _, row in g.iterrows():
            rd = self._round_metrics(row.to_dict())
            # Merchant category distribution only for P2M
            if rd.get("transaction_type") == "P2M" and "merchant_category" in df.columns:
                p2m_df = df[df["transaction_type"] == "P2M"]
                if len(p2m_df) > 0:
                    mc_dist = p2m_df["merchant_category"].value_counts(normalize=True) * 100
                    rd["merchant_category_distribution"] = {str(k): round(v, 2) for k, v in mc_dist.items()}
            types_data.append(rd)

        # Cross-type leaders and laggards
        key_metrics = ["success_rate_pct", "failure_rate_pct", "fraud_rate_pct",
                       "avg_amount_inr", "operational_health_score"]
        cross_type_leader: Dict[str, Any] = {}
        cross_type_laggard: Dict[str, Any] = {}
        for km in key_metrics:
            if km in g.columns:
                if km in ("failure_rate_pct", "fraud_rate_pct"):
                    lid = g[km].idxmin()
                    lagid = g[km].idxmax()
                else:
                    lid = g[km].idxmax()
                    lagid = g[km].idxmin()
                cross_type_leader[km] = {
                    "type": str(g.loc[lid, "transaction_type"]),
                    "value": round(float(g.loc[lid, km]), 2),
                }
                cross_type_laggard[km] = {
                    "type": str(g.loc[lagid, "transaction_type"]),
                    "value": round(float(g.loc[lagid, km]), 2),
                }

        overall_metrics = self._compute_metrics_single_pass(df)
        label = self._build_segment_label(filters) + " by transaction type"

        mode_specific = {
            "types": types_data,
            "cross_type_leader": cross_type_leader,
            "cross_type_laggard": cross_type_laggard,
            "type_count": len(types_data),
        }

        return self._base_output("transaction_type_profile", df, overall_metrics, params, mode_specific, label)

    # ------------------------------------------------------------------
    # 7. temporal_snapshot
    # ------------------------------------------------------------------

    def _mode_temporal_snapshot(self, params: Dict[str, Any]) -> str:
        """
        Metrics split by peak/off-peak hours and weekend/weekday.

        Args:
            params: Parameters dict with optional filters.

        Returns:
            JSON string with temporal segments and deltas.
        """
        filters = params.get("filters", [])
        df = self._apply_filters(self.df, filters)
        if len(df) == 0:
            return self._error_response("temporal_snapshot",
                                        "No records match the given filters.",
                                        "Broaden filter conditions.")

        self._ensure_mask_columns(df)

        # Peak = hours 18-21, off-peak = all others
        peak_mask = df["hour_of_day"].between(18, 21)
        weekend_mask = df["is_weekend"].astype(bool)

        peak_df = df.loc[peak_mask]
        offpeak_df = df.loc[~peak_mask]
        weekend_df = df.loc[weekend_mask]
        weekday_df = df.loc[~weekend_mask]

        peak_metrics = self._compute_metrics_single_pass(peak_df) if len(peak_df) > 0 else self._empty_metrics()
        offpeak_metrics = self._compute_metrics_single_pass(offpeak_df) if len(offpeak_df) > 0 else self._empty_metrics()
        weekend_metrics = self._compute_metrics_single_pass(weekend_df) if len(weekend_df) > 0 else self._empty_metrics()
        weekday_metrics = self._compute_metrics_single_pass(weekday_df) if len(weekday_df) > 0 else self._empty_metrics()

        # Deltas
        def compute_delta(a: Dict, b: Dict) -> Dict[str, Any]:
            delta = {}
            compare = ["success_rate_pct", "failure_rate_pct", "fraud_rate_pct",
                       "avg_amount_inr", "operational_health_score", "total_transactions",
                       "pending_rate_pct", "value_at_risk_pct"]
            for k in compare:
                av = self._to_num(a.get(k, 0))
                bv = self._to_num(b.get(k, 0))
                delta[k] = round(av - bv, 2)
            return delta

        peak_vs_offpeak = compute_delta(peak_metrics, offpeak_metrics)
        weekend_vs_weekday = compute_delta(weekend_metrics, weekday_metrics)

        # Worst temporal segment by health score
        segments = {
            "peak_hours": peak_metrics.get("operational_health_score", 0),
            "off_peak_hours": offpeak_metrics.get("operational_health_score", 0),
            "weekend": weekend_metrics.get("operational_health_score", 0),
            "weekday": weekday_metrics.get("operational_health_score", 0),
        }
        worst_segment = min(segments, key=segments.get)

        overall_metrics = self._compute_metrics_single_pass(df)
        label = self._build_segment_label(filters) + " temporal analysis"

        mode_specific = {
            "peak_hours": peak_metrics,
            "off_peak_hours": offpeak_metrics,
            "weekend": weekend_metrics,
            "weekday": weekday_metrics,
            "peak_vs_offpeak_delta": peak_vs_offpeak,
            "weekend_vs_weekday_delta": weekend_vs_weekday,
            "temporal_risk_assessment": {
                "worst_segment": worst_segment,
                "worst_health_score": round(segments[worst_segment], 2),
            },
        }

        return self._base_output("temporal_snapshot", df, overall_metrics, params, mode_specific, label)

    # ------------------------------------------------------------------
    # 8. funnel_analysis
    # ------------------------------------------------------------------

    def _mode_funnel_analysis(self, params: Dict[str, Any]) -> str:
        """
        Transaction conversion funnel with drop-off rates.

        Args:
            params: Parameters dict with optional filters.

        Returns:
            JSON string with funnel stages, drop-offs, value funnel.
        """
        filters = params.get("filters", [])
        df = self._apply_filters(self.df, filters)
        if len(df) == 0:
            return self._error_response("funnel_analysis",
                                        "No records match the given filters.",
                                        "Broaden filter conditions.")

        metrics = self._compute_metrics_single_pass(df)
        funnel = self._compute_funnel_stages(df)

        label = self._build_segment_label(filters)
        mode_specific = {"funnel": funnel}

        return self._base_output("funnel_analysis", df, metrics, params, mode_specific, label)

    # ------------------------------------------------------------------
    # 9. anomaly_snapshot
    # ------------------------------------------------------------------

    def _mode_anomaly_snapshot(self, params: Dict[str, Any]) -> str:
        """
        Standard snapshot with anomaly detection flags.

        Args:
            params: Parameters dict with optional filters and flag_threshold_multiplier.

        Returns:
            JSON string with metrics and anomaly report.
        """
        filters = params.get("filters", [])
        threshold = params.get("flag_threshold_multiplier", 1.5)
        df = self._apply_filters(self.df, filters)
        if len(df) == 0:
            return self._error_response("anomaly_snapshot",
                                        "No records match the given filters.",
                                        "Broaden filter conditions.")

        metrics = self._compute_metrics_single_pass(df)
        distributions = self._compute_distribution_metrics(df)
        anomalies = self._detect_anomalies(metrics, threshold)

        label = self._build_segment_label(filters)
        mode_specific = {
            "anomalies": anomalies,
            "distributions": distributions,
        }

        return self._base_output("anomaly_snapshot", df, metrics, params, mode_specific, label)

    # ------------------------------------------------------------------
    # 10. comparative_snapshot
    # ------------------------------------------------------------------

    def _mode_comparative_snapshot(self, params: Dict[str, Any]) -> str:
        """
        Run two snapshots and compare them side by side.

        Args:
            params: Parameters dict with segment_a_filters, segment_b_filters,
                    segment_a_label, segment_b_label.

        Returns:
            JSON string with both segments' metrics plus differences.
        """
        seg_a_filters = params.get("segment_a_filters", [])
        seg_b_filters = params.get("segment_b_filters", [])
        label_a = params.get("segment_a_label", "Segment A")
        label_b = params.get("segment_b_label", "Segment B")

        df_a = self._apply_filters(self.df, seg_a_filters)
        df_b = self._apply_filters(self.df, seg_b_filters)

        if len(df_a) == 0:
            return self._error_response("comparative_snapshot",
                                        f"No records match segment A filters ({label_a}).",
                                        "Check segment_a_filters.")
        if len(df_b) == 0:
            return self._error_response("comparative_snapshot",
                                        f"No records match segment B filters ({label_b}).",
                                        "Check segment_b_filters.")

        metrics_a = self._compute_metrics_single_pass(df_a)
        metrics_b = self._compute_metrics_single_pass(df_b)

        # Difference block
        compare_keys = [
            "total_transactions", "total_amount_inr", "avg_amount_inr", "median_amount_inr",
            "success_rate_pct", "failure_rate_pct", "pending_rate_pct",
            "fraud_rate_pct", "fraud_by_value_rate_pct",
            "effective_success_rate_pct", "problematic_rate_pct",
            "value_at_risk_pct", "operational_health_score",
            "data_share_pct", "amount_share_pct", "wallet_concentration_ratio",
            "recovery_opportunity_inr",
        ]

        positive_is_better = {
            "total_transactions", "total_amount_inr", "avg_amount_inr", "median_amount_inr",
            "success_rate_pct", "effective_success_rate_pct", "operational_health_score",
            "data_share_pct", "amount_share_pct",
        }

        difference_block: Dict[str, Any] = {}
        a_wins = 0
        b_wins = 0

        for k in compare_keys:
            va = self._to_num(metrics_a.get(k, 0))
            vb = self._to_num(metrics_b.get(k, 0))
            abs_diff = round(va - vb, 2)
            pct_diff = round(abs_diff / vb * 100, 2) if vb != 0 else 0.0

            if k in positive_is_better:
                winner = label_a if va > vb else (label_b if vb > va else "Tie")
            else:
                winner = label_a if va < vb else (label_b if vb < va else "Tie")

            if winner == label_a:
                a_wins += 1
            elif winner == label_b:
                b_wins += 1

            difference_block[k] = {
                "value_a": va,
                "value_b": vb,
                "absolute_difference": abs_diff,
                "percentage_difference": pct_diff,
                "winner": winner,
            }

        overall_winner = label_a if a_wins > b_wins else (label_b if b_wins > a_wins else "Tie")
        margin = abs(a_wins - b_wins)
        stat_note = (
            f"{label_a} wins {a_wins} metrics, {label_b} wins {b_wins} metrics. "
            + ("The margin is narrow; differences may not be operationally significant." if margin <= 2
               else "The margin is clear; one segment meaningfully outperforms the other.")
        )

        # Use combined metrics for the base output summary
        combined_df = pd.concat([df_a, df_b], ignore_index=True)
        overall_metrics = self._compute_metrics_single_pass(combined_df)
        label = f"{label_a} vs {label_b}"

        mode_specific = {
            "segment_a": {
                "label": label_a,
                "filters": seg_a_filters,
                "metrics": metrics_a,
                "record_count": int(metrics_a.get("total_transactions", len(df_a))),
            },
            "segment_b": {
                "label": label_b,
                "filters": seg_b_filters,
                "metrics": metrics_b,
                "record_count": int(metrics_b.get("total_transactions", len(df_b))),
            },
            "difference_block": difference_block,
            "head_to_head_score": {
                label_a: a_wins,
                label_b: b_wins,
            },
            "overall_winner": overall_winner,
            "statistical_note": stat_note,
        }

        return self._base_output("comparative_snapshot", combined_df, overall_metrics, params, mode_specific, label)


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------

def create_multi_metric_tool() -> StructuredTool:
    """
    Create the multi-metric LangChain StructuredTool.

    Returns:
        A StructuredTool wrapping MultiMetricTool.analyze.
    """
    tool_instance = MultiMetricTool()
    return StructuredTool.from_function(
        func=tool_instance.analyze,
        name="multi_metric_tool",
        description=(
            "For ALL multi-KPI questions requiring several metrics at once on the same dataset. "
            "Use this for 'complete picture,' 'full snapshot,' 'health check,' 'overall performance,' "
            "'give me all metrics,' 'how is X performing,' and any question that would otherwise "
            "require multiple separate tool calls. Computes count, average amount, failure rate, "
            "fraud rate, success rate, and 20+ more metrics in a single pass. "
            "Input: analysis_mode (string: snapshot, grouped_snapshot, multi_group_snapshot, "
            "segment_profile, health_scorecard, transaction_type_profile, temporal_snapshot, "
            "funnel_analysis, anomaly_snapshot, comparative_snapshot) and parameters (JSON string "
            "with filters, group_by, include_benchmarks, metrics_to_include, etc.)."
        ),
        args_schema=MultiMetricInput,
    )
