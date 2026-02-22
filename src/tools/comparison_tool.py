"""
Comparison Tool for PayInsight AI

This module provides comprehensive segment comparison capabilities for transaction data.
It handles all "A vs B", "which is better/worse", ranking, and cross-segment comparison
queries with built-in statistical significance testing, effect sizes, and confidence intervals.

Author: Team primeFactors
"""

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
import pandas as pd
import numpy as np
from scipy import stats
import json
import math
from typing import Any, Dict, List, Optional, Tuple
from src.utils.data_loader import data_loader


class ComparisonInput(BaseModel):
    """Input schema for comparison tool."""

    comparison_type: str = Field(
        description=(
            "Type of comparison: head_to_head, multi_segment, cross_segment, "
            "metric_comparison, conditional_comparison, ranked_comparison, "
            "bank_vs_bank, device_network_matrix"
        )
    )
    parameters: str = Field(
        description=(
            "JSON string with segment definitions: segment_column, segment_a, "
            "segment_b, metric, filters, include_statistical_tests, confidence_level, "
            "top_n, column_a, column_b, value_a, value_b, secondary_metrics"
        )
    )


class ComparisonTool:
    """
    Comprehensive segment comparison tool for transaction data.

    Handles head-to-head, multi-segment, cross-segment, metric, conditional,
    ranked, bank-vs-bank, and device-network matrix comparisons with full
    statistical validation (Chi-Square, T-Test, Cohen's d, Relative Risk,
    Wilson confidence intervals).
    """

    def __init__(self) -> None:
        """Initialize ComparisonTool with data from the singleton loader."""
        self.df: pd.DataFrame = data_loader.load_data()
        self.total_records: int = len(self.df)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def compare(self, comparison_type: str, parameters: str) -> str:
        """
        Main entry point for segment comparisons.

        Args:
            comparison_type: The type of comparison to perform.
            parameters: JSON string containing segment definitions and options.

        Returns:
            JSON string with comparison results in standardised format.
        """
        try:
            params: Dict = json.loads(parameters) if parameters else {}
        except json.JSONDecodeError as exc:
            return self._error_response(
                comparison_type,
                f"Invalid JSON in parameters: {exc}",
                "Ensure parameters is a valid JSON string",
            )

        dispatch = {
            "head_to_head": self._compare_head_to_head,
            "multi_segment": self._compare_multi_segment,
            "cross_segment": self._compare_cross_segment,
            "metric_comparison": self._compare_metric,
            "conditional_comparison": self._compare_conditional,
            "ranked_comparison": self._compare_ranked,
            "bank_vs_bank": self._compare_bank_vs_bank,
            "device_network_matrix": self._compare_device_network_matrix,
        }

        if comparison_type not in dispatch:
            return self._error_response(
                comparison_type,
                f"Unknown comparison_type: {comparison_type}",
                f"Valid types: {', '.join(dispatch.keys())}",
            )

        try:
            return dispatch[comparison_type](params)
        except Exception as exc:
            return self._error_response(
                comparison_type,
                f"Comparison failed: {exc}",
                "Check your parameters and try again",
            )

    # ------------------------------------------------------------------
    # Helpers – filters, metrics, stats
    # ------------------------------------------------------------------

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

    def _compute_segment_metrics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Compute the full standard metric suite for a segment DataFrame.

        Args:
            df: Filtered DataFrame representing one segment.

        Returns:
            Dictionary of all computed metrics.
        """
        n = len(df)
        if n == 0:
            return self._empty_metrics()

        status = df["transaction_status"].value_counts()
        success = int(status.get("SUCCESS", 0))
        failed = int(status.get("FAILED", 0))
        pending = int(status.get("PENDING", 0))

        amt = df["amount_inr"].dropna()
        fraud_count = int(df["fraud_flag"].sum())
        fraud_amount = float(df.loc[df["fraud_flag"] == True, "amount_inr"].sum()) if "fraud_flag" in df.columns else 0.0  # noqa: E712
        total_amount = float(amt.sum())

        unique_days = df["timestamp"].dt.date.nunique() if "timestamp" in df.columns and pd.api.types.is_datetime64_any_dtype(df["timestamp"]) else 1

        return {
            # Volume
            "total_transactions": n,
            "share_of_total": round(n / self.total_records * 100, 2),
            "daily_avg_transactions": round(n / max(unique_days, 1), 2),
            # Status
            "success_count": success,
            "success_rate": round(success / n * 100, 2),
            "failed_count": failed,
            "failure_rate": round(failed / n * 100, 2),
            "pending_count": pending,
            "pending_rate": round(pending / n * 100, 2),
            # Amount
            "avg_amount": round(float(amt.mean()), 2) if len(amt) > 0 else 0.0,
            "median_amount": round(float(amt.median()), 2) if len(amt) > 0 else 0.0,
            "total_amount": round(total_amount, 2),
            "amount_std": round(float(amt.std()), 2) if len(amt) > 1 else 0.0,
            "p75_amount": round(float(amt.quantile(0.75)), 2) if len(amt) > 0 else 0.0,
            "p95_amount": round(float(amt.quantile(0.95)), 2) if len(amt) > 0 else 0.0,
            # Risk
            "fraud_count": fraud_count,
            "fraud_rate": round(fraud_count / n * 100, 2),
            "fraud_by_value_rate": round(fraud_amount / total_amount * 100, 2) if total_amount > 0 else 0.0,
        }

    def _empty_metrics(self) -> Dict[str, Any]:
        """Return a zeroed-out metric suite for empty segments."""
        keys = [
            "total_transactions", "share_of_total", "daily_avg_transactions",
            "success_count", "success_rate", "failed_count", "failure_rate",
            "pending_count", "pending_rate", "avg_amount", "median_amount",
            "total_amount", "amount_std", "p75_amount", "p95_amount",
            "fraud_count", "fraud_rate", "fraud_by_value_rate",
        ]
        return {k: 0 for k in keys}

    # --- Statistical tests ---------------------------------------------------

    def _run_chi_square(
        self,
        df_a: pd.DataFrame,
        df_b: pd.DataFrame,
        confidence: float = 0.95,
    ) -> Dict[str, Any]:
        """
        Chi-Square test of independence on transaction status distributions.

        Args:
            df_a: Segment A DataFrame.
            df_b: Segment B DataFrame.
            confidence: Confidence level (default 0.95).

        Returns:
            Dict with chi2, p_value, dof, significance flag and statement.
        """
        alpha = 1 - confidence
        statuses = ["SUCCESS", "FAILED", "PENDING"]
        counts_a = df_a["transaction_status"].value_counts()
        counts_b = df_b["transaction_status"].value_counts()
        table = np.array([[counts_a.get(s, 0) for s in statuses],
                          [counts_b.get(s, 0) for s in statuses]])
        # Drop columns that are entirely zero
        table = table[:, table.sum(axis=0) > 0]
        if table.shape[1] < 2 or table.sum() == 0:
            return {"chi2_statistic": None, "p_value": None, "degrees_of_freedom": None,
                    "is_significant": False, "significance_statement": "Insufficient data for Chi-Square test"}
        chi2, p, dof, _ = stats.chi2_contingency(table)
        return {
            "chi2_statistic": round(float(chi2), 4),
            "p_value": round(float(p), 6),
            "degrees_of_freedom": int(dof),
            "is_significant": p < alpha,
            "significance_statement": (
                "Statistically significant difference in outcome distributions"
                if p < alpha
                else "No statistically significant difference in outcome distributions"
            ),
        }

    def _run_ttest(
        self,
        arr_a: np.ndarray,
        arr_b: np.ndarray,
        confidence: float = 0.95,
    ) -> Dict[str, Any]:
        """
        Independent two-sample T-Test on amount distributions.

        Args:
            arr_a: Amount array for segment A.
            arr_b: Amount array for segment B.
            confidence: Confidence level.

        Returns:
            Dict with t-statistic, p-value, significance flag.
        """
        alpha = 1 - confidence
        if len(arr_a) < 2 or len(arr_b) < 2:
            return {"t_statistic": None, "p_value": None, "is_significant": False,
                    "significance_statement": "Insufficient data for T-Test"}
        t_stat, p = stats.ttest_ind(arr_a, arr_b, equal_var=False)
        return {
            "t_statistic": round(float(t_stat), 4),
            "p_value": round(float(p), 6),
            "is_significant": p < alpha,
            "significance_statement": (
                "Statistically significant difference in transaction amounts"
                if p < alpha
                else "No statistically significant difference in transaction amounts"
            ),
        }

    def _compute_cohens_d(self, arr_a: np.ndarray, arr_b: np.ndarray) -> Dict[str, Any]:
        """
        Compute Cohen's d effect size between two amount arrays.

        Args:
            arr_a: Amount array for segment A.
            arr_b: Amount array for segment B.

        Returns:
            Dict with cohens_d value and effect_size_label.
        """
        if len(arr_a) < 2 or len(arr_b) < 2:
            return {"cohens_d": None, "effect_size_label": "Insufficient data"}
        n_a, n_b = len(arr_a), len(arr_b)
        var_a, var_b = arr_a.var(ddof=1), arr_b.var(ddof=1)
        pooled_std = math.sqrt(((n_a - 1) * var_a + (n_b - 1) * var_b) / (n_a + n_b - 2))
        if pooled_std == 0:
            return {"cohens_d": 0.0, "effect_size_label": "Negligible"}
        d = float((arr_a.mean() - arr_b.mean()) / pooled_std)
        abs_d = abs(d)
        label = "Negligible" if abs_d < 0.2 else "Small" if abs_d < 0.5 else "Medium" if abs_d < 0.8 else "Large"
        return {"cohens_d": round(d, 4), "effect_size_label": label}

    def _compute_relative_risk(
        self,
        rate_a: float,
        rate_b: float,
        label_a: str,
        label_b: str,
        metric_name: str = "failure",
    ) -> Dict[str, Any]:
        """
        Compute relative risk ratio between two rates.

        Args:
            rate_a: Rate (%) for segment A.
            rate_b: Rate (%) for segment B.
            label_a: Human-readable label for segment A.
            label_b: Human-readable label for segment B.
            metric_name: Name of the metric (for interpretation text).

        Returns:
            Dict with relative_risk and risk_interpretation.
        """
        if rate_b == 0:
            rr = float("inf") if rate_a > 0 else 1.0
        else:
            rr = round(rate_a / rate_b, 4)
        if rr > 1:
            interp = f"{label_a} users are {rr:.2f}x more likely to experience a {metric_name} than {label_b} users"
        elif rr < 1:
            inv = round(1 / rr, 2) if rr > 0 else float("inf")
            interp = f"{label_b} users are {inv:.2f}x more likely to experience a {metric_name} than {label_a} users"
        else:
            interp = f"{label_a} and {label_b} have equal {metric_name} risk"
        return {"relative_risk": round(rr, 4), "risk_interpretation": interp}

    def _compute_wilson_ci(
        self,
        successes: int,
        total: int,
        confidence: float = 0.95,
    ) -> Dict[str, float]:
        """
        Wilson Score confidence interval for a proportion.

        Args:
            successes: Number of successes (or events).
            total: Total trials.
            confidence: Confidence level.

        Returns:
            Dict with lower_ci and upper_ci as percentages.
        """
        if total == 0:
            return {"lower_ci": 0.0, "upper_ci": 0.0}
        p_hat = successes / total
        z = stats.norm.ppf(1 - (1 - confidence) / 2)
        denom = 1 + z ** 2 / total
        centre = (p_hat + z ** 2 / (2 * total)) / denom
        spread = z * math.sqrt((p_hat * (1 - p_hat) + z ** 2 / (4 * total)) / total) / denom
        return {
            "lower_ci": round(max(0, (centre - spread)) * 100, 2),
            "upper_ci": round(min(1, (centre + spread)) * 100, 2),
        }

    # --- Difference / verdict builders ----------------------------------------

    def _build_difference_block(
        self,
        metrics_a: Dict,
        metrics_b: Dict,
        label_a: str,
        label_b: str,
    ) -> Dict[str, Any]:
        """
        Compute per-metric differences between two segments.

        Args:
            metrics_a: Full metric suite for segment A.
            metrics_b: Full metric suite for segment B.
            label_a: Human-readable name of segment A.
            label_b: Human-readable name of segment B.

        Returns:
            Dict keyed by metric name with abs_diff, pct_diff, ratio, winner.
        """
        compare_keys = [
            "success_rate", "failure_rate", "pending_rate",
            "avg_amount", "median_amount", "total_amount",
            "fraud_rate", "fraud_by_value_rate",
            "total_transactions",
        ]
        diffs: Dict[str, Any] = {}
        for key in compare_keys:
            val_a = metrics_a.get(key, 0)
            val_b = metrics_b.get(key, 0)
            abs_diff = round(val_a - val_b, 2)
            pct_diff = round((val_a - val_b) / val_b * 100, 2) if val_b != 0 else 0.0
            ratio = round(val_a / val_b, 4) if val_b != 0 else 0.0
            # For "bad" metrics, lower is better
            lower_is_better = key in ("failure_rate", "pending_rate", "fraud_rate", "fraud_by_value_rate")
            if abs_diff == 0:
                winner = "Tie"
            elif lower_is_better:
                winner = label_a if val_a < val_b else label_b
            else:
                winner = label_a if val_a > val_b else label_b
            diffs[key] = {
                "segment_a_value": val_a,
                "segment_b_value": val_b,
                "absolute_difference": abs_diff,
                "percentage_difference": pct_diff,
                "ratio": ratio,
                "winner": winner,
            }
        return diffs

    def _generate_verdict(
        self,
        diffs: Dict,
        label_a: str,
        label_b: str,
        stat_tests: Dict,
    ) -> str:
        """
        Produce a plain-English verdict based on differences and stat tests.

        Args:
            diffs: Output of _build_difference_block.
            label_a: Segment A label.
            label_b: Segment B label.
            stat_tests: Statistical test results dict.

        Returns:
            A specific, data-driven verdict string.
        """
        wins_a = sum(1 for v in diffs.values() if v["winner"] == label_a)
        wins_b = sum(1 for v in diffs.values() if v["winner"] == label_b)

        overall_winner = label_a if wins_a > wins_b else label_b if wins_b > wins_a else "Mixed"

        # Find strongest advantage
        best_metric = ""
        best_pct = 0.0
        for k, v in diffs.items():
            if abs(v["percentage_difference"]) > abs(best_pct):
                best_pct = v["percentage_difference"]
                best_metric = k

        # Stat significance note
        chi_sig = stat_tests.get("chi_square", {}).get("is_significant")
        chi_p = stat_tests.get("chi_square", {}).get("p_value")

        sig_note = ""
        if chi_sig is True:
            sig_note = f" — a statistically significant difference (p={chi_p})"
        elif chi_sig is False and chi_p is not None:
            sig_note = f" — though the difference is not statistically significant (p={chi_p})"

        # Build verdict
        fail_a = diffs.get("failure_rate", {}).get("segment_a_value", "?")
        fail_b = diffs.get("failure_rate", {}).get("segment_b_value", "?")
        avg_a = diffs.get("avg_amount", {}).get("segment_a_value", "?")
        avg_b = diffs.get("avg_amount", {}).get("segment_b_value", "?")

        if overall_winner == "Mixed":
            verdict = (
                f"Results are mixed: {label_a} wins on {wins_a} metrics while {label_b} wins on {wins_b}. "
                f"{label_a} has a failure rate of {fail_a}% vs {label_b}'s {fail_b}%{sig_note}. "
                f"However, {label_a} averages ₹{avg_a} per transaction vs {label_b}'s ₹{avg_b}."
            )
        else:
            loser = label_b if overall_winner == label_a else label_a
            opp_fail = fail_b if overall_winner == label_a else fail_a
            own_fail = fail_a if overall_winner == label_a else fail_b
            verdict = (
                f"{overall_winner} outperforms {loser} overall, winning {max(wins_a, wins_b)} of "
                f"{wins_a + wins_b} metrics. "
                f"Failure rate: {own_fail}% vs {opp_fail}%{sig_note}. "
                f"Strongest difference is on {best_metric} ({abs(best_pct):.1f}% gap)."
            )

        return verdict

    # --- Full stat-test bundle for head-to-head --------------------------------

    def _run_all_statistical_tests(
        self,
        df_a: pd.DataFrame,
        df_b: pd.DataFrame,
        metrics_a: Dict,
        metrics_b: Dict,
        label_a: str,
        label_b: str,
        confidence: float,
    ) -> Dict[str, Any]:
        """
        Run all statistical tests for a head-to-head comparison.

        Args:
            df_a, df_b: Segment DataFrames.
            metrics_a, metrics_b: Computed metric suites.
            label_a, label_b: Segment labels.
            confidence: Confidence level for tests.

        Returns:
            Dict with chi_square, ttest, cohens_d, relative_risk_failure,
            relative_risk_fraud, confidence_intervals keys.
        """
        result: Dict[str, Any] = {}

        # Chi-Square
        result["chi_square"] = self._run_chi_square(df_a, df_b, confidence)

        # T-Test on amounts
        amt_a = df_a["amount_inr"].dropna().values
        amt_b = df_b["amount_inr"].dropna().values
        result["ttest_amount"] = self._run_ttest(amt_a, amt_b, confidence)

        # Cohen's d
        result["cohens_d"] = self._compute_cohens_d(amt_a, amt_b)

        # Relative Risk – failure
        result["relative_risk_failure"] = self._compute_relative_risk(
            metrics_a["failure_rate"], metrics_b["failure_rate"],
            label_a, label_b, "failure",
        )

        # Relative Risk – fraud
        result["relative_risk_fraud"] = self._compute_relative_risk(
            metrics_a["fraud_rate"], metrics_b["fraud_rate"],
            label_a, label_b, "fraud flag",
        )

        # Confidence Intervals
        n_a, n_b = len(df_a), len(df_b)
        result["confidence_intervals"] = {
            "segment_a": {
                "failure_rate": self._compute_wilson_ci(metrics_a["failed_count"], n_a, confidence),
                "success_rate": self._compute_wilson_ci(metrics_a["success_count"], n_a, confidence),
                "fraud_rate": self._compute_wilson_ci(metrics_a["fraud_count"], n_a, confidence),
            },
            "segment_b": {
                "failure_rate": self._compute_wilson_ci(metrics_b["failed_count"], n_b, confidence),
                "success_rate": self._compute_wilson_ci(metrics_b["success_count"], n_b, confidence),
                "fraud_rate": self._compute_wilson_ci(metrics_b["fraud_count"], n_b, confidence),
            },
        }

        return result

    # ------------------------------------------------------------------
    # Comparison types
    # ------------------------------------------------------------------

    def _compare_head_to_head(self, params: Dict) -> str:
        """
        Direct comparison of two segment values on one column.

        Args:
            params: Dict with segment_column, segment_a, segment_b, metric, etc.

        Returns:
            JSON string with full comparison output.
        """
        col = data_loader.resolve_column(params.get("segment_column", ""))
        val_a = params.get("segment_a", "")
        val_b = params.get("segment_b", "")
        metric = params.get("metric", "failure_rate")
        filters = params.get("filters", [])
        include_stats = params.get("include_statistical_tests", True)
        confidence = params.get("confidence_level", 0.95)

        df = self._apply_filters(self.df, filters)

        if col not in df.columns:
            return self._error_response("head_to_head", f"Column '{col}' not found", "Check column name")

        df_a = df[df[col] == val_a]
        df_b = df[df[col] == val_b]

        if df_a.empty:
            return self._error_response("head_to_head", f"No data for {col}={val_a}", "Check segment value")
        if df_b.empty:
            return self._error_response("head_to_head", f"No data for {col}={val_b}", "Check segment value")

        metrics_a = self._compute_segment_metrics(df_a)
        metrics_b = self._compute_segment_metrics(df_b)

        diffs = self._build_difference_block(metrics_a, metrics_b, str(val_a), str(val_b))

        stat_tests: Dict = {}
        if include_stats:
            stat_tests = self._run_all_statistical_tests(
                df_a, df_b, metrics_a, metrics_b, str(val_a), str(val_b), confidence,
            )

        verdict = self._generate_verdict(diffs, str(val_a), str(val_b), stat_tests)

        # Summary
        summary = self._build_summary(diffs, metrics_a, metrics_b, str(val_a), str(val_b), metric, stat_tests)

        return self._success_response(
            "head_to_head",
            col,
            filters,
            len(df_a) + len(df_b),
            {
                "segment_a": {"label": str(val_a), "record_count": len(df_a), "metrics": metrics_a},
                "segment_b": {"label": str(val_b), "record_count": len(df_b), "metrics": metrics_b},
            },
            {"differences": diffs, "statistical_tests": stat_tests, "verdict": verdict},
            summary,
        )

    def _compare_multi_segment(self, params: Dict) -> str:
        """
        Compare all unique values of a column against each other.

        Args:
            params: Dict with segment_column, metric, top_n, filters.

        Returns:
            JSON string with ranked multi-segment results.
        """
        col = data_loader.resolve_column(params.get("segment_column", ""))
        metric = params.get("metric", "failure_rate")
        top_n = params.get("top_n")
        filters = params.get("filters", [])

        df = self._apply_filters(self.df, filters)

        if col not in df.columns:
            return self._error_response("multi_segment", f"Column '{col}' not found", "Check column name")

        # Default top_n for states
        if top_n is None and col == "sender_state":
            top_n = 10

        # Compute metrics for each segment
        segments: List[Dict] = []
        for val, grp in df.groupby(col):
            m = self._compute_segment_metrics(grp)
            segments.append({"label": str(val), "record_count": len(grp), "metrics": m})

        # Sort
        higher_is_better = metric in ("success_rate", "total_transactions", "avg_amount", "total_amount", "total_volume")
        segments.sort(key=lambda s: s["metrics"].get(metric, 0), reverse=higher_is_better)

        # Add rank, vs_average, gap_to_leader
        metric_values = [s["metrics"].get(metric, 0) for s in segments]
        avg_val = float(np.mean(metric_values)) if metric_values else 0.0
        leader_val = metric_values[0] if metric_values else 0.0

        for i, seg in enumerate(segments):
            seg["rank"] = i + 1
            val = seg["metrics"].get(metric, 0)
            seg["vs_average"] = round(val - avg_val, 2)
            seg["gap_to_leader"] = {
                "absolute": round(val - leader_val, 2),
                "percentage": round((val - leader_val) / leader_val * 100, 2) if leader_val != 0 else 0.0,
            }

        # Age order for age groups
        if col == "sender_age_group":
            age_order = ["18-25", "26-35", "36-45", "46-55", "56+"]
            age_ordered = sorted(segments, key=lambda s: age_order.index(s["label"]) if s["label"] in age_order else 99)
            for seg in segments:
                seg["age_ordered_rank"] = next(
                    (i + 1 for i, a in enumerate(age_ordered) if a["label"] == seg["label"]), None
                )

        if top_n:
            segments = segments[:top_n]

        best = segments[0]["label"] if segments else "N/A"
        worst = segments[-1]["label"] if segments else "N/A"
        best_val = segments[0]["metrics"].get(metric, 0) if segments else 0
        worst_val = segments[-1]["metrics"].get(metric, 0) if segments else 0

        summary = {
            "key_finding": (
                f"{best} leads with {metric} of {best_val}, "
                f"while {worst} trails at {worst_val} across {len(segments)} segments"
            ),
            "winner_overall": best,
            "strongest_advantage": metric,
            "concern_area": f"{worst} significantly underperforms",
        }

        return json.dumps({
            "success": True,
            "comparison_type": "multi_segment",
            "segment_column": col,
            "filters_applied": filters,
            "total_records_analyzed": len(df),
            "segments": segments,
            "comparison": {"metric_used": metric, "average_value": round(avg_val, 2)},
            "summary": summary,
            "metadata": {
                "data_coverage_pct": round(len(df) / self.total_records * 100, 2),
                "execution_note": f"Ranked by {metric} ({'descending' if higher_is_better else 'ascending'})",
            },
        }, default=str)

    def _compare_cross_segment(self, params: Dict) -> str:
        """
        Compare two groups defined by different column-value pairs.

        Args:
            params: Dict with column_a, value_a, column_b, value_b, metric, etc.

        Returns:
            JSON string with cross-segment comparison.
        """
        col_a = data_loader.resolve_column(params.get("column_a", ""))
        val_a = params.get("value_a", "")
        col_b = data_loader.resolve_column(params.get("column_b", ""))
        val_b = params.get("value_b", "")
        metric = params.get("metric", "failure_rate")
        filters = params.get("filters", [])
        include_stats = params.get("include_statistical_tests", True)
        confidence = params.get("confidence_level", 0.95)

        df = self._apply_filters(self.df, filters)

        df_a = df[df[col_a] == val_a] if col_a in df.columns else pd.DataFrame()
        df_b = df[df[col_b] == val_b] if col_b in df.columns else pd.DataFrame()

        if df_a.empty:
            return self._error_response("cross_segment", f"No data for {col_a}={val_a}", "Check value")
        if df_b.empty:
            return self._error_response("cross_segment", f"No data for {col_b}={val_b}", "Check value")

        label_a = f"{val_a} ({col_a})"
        label_b = f"{val_b} ({col_b})"

        overlap = len(pd.merge(df_a, df_b, how="inner", on="transaction_id")) if "transaction_id" in df.columns else 0

        metrics_a = self._compute_segment_metrics(df_a)
        metrics_b = self._compute_segment_metrics(df_b)
        diffs = self._build_difference_block(metrics_a, metrics_b, label_a, label_b)

        stat_tests: Dict = {}
        if include_stats:
            stat_tests = self._run_all_statistical_tests(
                df_a, df_b, metrics_a, metrics_b, label_a, label_b, confidence,
            )

        verdict = self._generate_verdict(diffs, label_a, label_b, stat_tests)
        summary = self._build_summary(diffs, metrics_a, metrics_b, label_a, label_b, metric, stat_tests)

        resp = self._success_response(
            "cross_segment", f"{col_a} vs {col_b}", filters, len(df_a) + len(df_b),
            {
                "segment_a": {"label": label_a, "record_count": len(df_a), "metrics": metrics_a},
                "segment_b": {"label": label_b, "record_count": len(df_b), "metrics": metrics_b},
            },
            {"differences": diffs, "statistical_tests": stat_tests, "verdict": verdict},
            summary,
        )
        # Inject overlap
        parsed = json.loads(resp)
        parsed["metadata"]["overlap_count"] = overlap
        return json.dumps(parsed, default=str)

    def _compare_metric(self, params: Dict) -> str:
        """
        Side-by-side comparison table of all metrics between two segments.

        Args:
            params: Same as head_to_head.

        Returns:
            JSON string with metric comparison table format.
        """
        # Reuse head_to_head internally
        h2h = json.loads(self._compare_head_to_head(params))
        if not h2h.get("success"):
            return json.dumps(h2h, default=str)

        # Reshape into a table structure
        diffs = h2h.get("comparison", {}).get("differences", {})
        table_rows: List[Dict] = []
        for metric_name, diff_info in diffs.items():
            table_rows.append({
                "metric": metric_name,
                "segment_a_value": diff_info["segment_a_value"],
                "segment_b_value": diff_info["segment_b_value"],
                "absolute_difference": diff_info["absolute_difference"],
                "percentage_difference": diff_info["percentage_difference"],
                "winner": diff_info["winner"],
            })

        h2h["comparison_type"] = "metric_comparison"
        h2h["comparison_table"] = table_rows
        return json.dumps(h2h, default=str)

    def _compare_conditional(self, params: Dict) -> str:
        """
        Compare two segments within a filtered subset, and show filter impact.

        Args:
            params: Same as head_to_head plus required filters.

        Returns:
            JSON string with filtered comparison plus filter impact analysis.
        """
        col = data_loader.resolve_column(params.get("segment_column", ""))
        val_a = params.get("segment_a", "")
        val_b = params.get("segment_b", "")
        metric = params.get("metric", "failure_rate")
        filters = params.get("filters", [])
        include_stats = params.get("include_statistical_tests", True)
        confidence = params.get("confidence_level", 0.95)

        # Unfiltered comparison
        unfiltered_params = {**params, "filters": []}
        unfiltered_result = json.loads(self._compare_head_to_head(unfiltered_params))

        # Filtered comparison
        df_filtered = self._apply_filters(self.df, filters)
        if col not in df_filtered.columns:
            return self._error_response("conditional_comparison", f"Column '{col}' not found", "Check column name")

        df_a = df_filtered[df_filtered[col] == val_a]
        df_b = df_filtered[df_filtered[col] == val_b]

        if df_a.empty or df_b.empty:
            return self._error_response(
                "conditional_comparison",
                f"After filtering, segment(s) have no data (A={len(df_a)}, B={len(df_b)})",
                "Try less restrictive filters",
            )

        metrics_a = self._compute_segment_metrics(df_a)
        metrics_b = self._compute_segment_metrics(df_b)
        diffs = self._build_difference_block(metrics_a, metrics_b, str(val_a), str(val_b))

        stat_tests: Dict = {}
        if include_stats:
            stat_tests = self._run_all_statistical_tests(
                df_a, df_b, metrics_a, metrics_b, str(val_a), str(val_b), confidence,
            )

        verdict = self._generate_verdict(diffs, str(val_a), str(val_b), stat_tests)
        summary = self._build_summary(diffs, metrics_a, metrics_b, str(val_a), str(val_b), metric, stat_tests)

        # Filter impact
        unf_winner = unfiltered_result.get("summary", {}).get("winner_overall", "")
        filt_winner = summary.get("winner_overall", "")
        filter_changed_winner = unf_winner != filt_winner

        filter_desc = ", ".join([f"{f['column']} {f.get('operator', '==')} {f['value']}" for f in filters])
        filter_context = {
            "filter_description": filter_desc,
            "original_dataset_size": self.total_records,
            "filtered_dataset_size": len(df_filtered),
            "reduction_pct": round((1 - len(df_filtered) / self.total_records) * 100, 2),
            "filter_changed_winner": filter_changed_winner,
            "unfiltered_winner": unf_winner,
            "filtered_winner": filt_winner,
        }

        resp = self._success_response(
            "conditional_comparison", col, filters, len(df_a) + len(df_b),
            {
                "segment_a": {"label": str(val_a), "record_count": len(df_a), "metrics": metrics_a},
                "segment_b": {"label": str(val_b), "record_count": len(df_b), "metrics": metrics_b},
            },
            {"differences": diffs, "statistical_tests": stat_tests, "verdict": verdict},
            summary,
        )
        parsed = json.loads(resp)
        parsed["filter_context"] = filter_context
        return json.dumps(parsed, default=str)

    def _compare_ranked(self, params: Dict) -> str:
        """
        Rank all values of a column by a chosen metric with gap analysis.

        Args:
            params: Dict with segment_column, metric, top_n, filters.

        Returns:
            JSON string with ranked segments and cliff-point detection.
        """
        col = data_loader.resolve_column(params.get("segment_column", ""))
        metric = params.get("metric", "failure_rate")
        top_n = params.get("top_n")
        filters = params.get("filters", [])

        df = self._apply_filters(self.df, filters)

        if col not in df.columns:
            return self._error_response("ranked_comparison", f"Column '{col}' not found", "Check column name")

        # Default top_n for states
        if top_n is None and col == "sender_state":
            top_n = 10

        segments: List[Dict] = []
        for val, grp in df.groupby(col):
            m = self._compute_segment_metrics(grp)
            segments.append({"label": str(val), "record_count": len(grp), "metrics": m})

        # Sort: higher_is_better for positive metrics, lower_is_better for negative metrics
        higher_is_better = metric in ("success_rate", "total_transactions", "avg_amount", "total_amount", "daily_avg_transactions")
        segments.sort(key=lambda s: s["metrics"].get(metric, 0), reverse=higher_is_better)

        total_segments = len(segments)
        metric_values = [s["metrics"].get(metric, 0) for s in segments]

        for i, seg in enumerate(segments):
            seg["rank"] = i + 1
            seg["percentile"] = round((total_segments - i) / total_segments * 100, 2)
            # Consecutive gap
            if i > 0:
                gap = abs(metric_values[i] - metric_values[i - 1])
                seg["gap_from_previous"] = round(gap, 2)
            else:
                seg["gap_from_previous"] = 0.0

        # Detect cliff points (gap > 1.5 * std of all gaps)
        gaps = [s["gap_from_previous"] for s in segments[1:]]
        if gaps:
            gap_mean = float(np.mean(gaps))
            gap_std = float(np.std(gaps))
            cliff_threshold = gap_mean + 1.5 * gap_std
            for seg in segments:
                seg["is_cliff_point"] = seg["gap_from_previous"] > cliff_threshold
        else:
            for seg in segments:
                seg["is_cliff_point"] = False

        # Age ordering
        if col == "sender_age_group":
            age_order = ["18-25", "26-35", "36-45", "46-55", "56+"]
            for seg in segments:
                seg["age_position"] = age_order.index(seg["label"]) + 1 if seg["label"] in age_order else None

        if top_n:
            segments = segments[:top_n]

        best = segments[0]["label"] if segments else "N/A"
        worst = segments[-1]["label"] if segments else "N/A"
        best_val = segments[0]["metrics"].get(metric, 0) if segments else 0
        worst_val = segments[-1]["metrics"].get(metric, 0) if segments else 0

        summary = {
            "key_finding": (
                f"{best} ranks #1 with {metric} of {best_val}, "
                f"while {worst} is last at {worst_val} "
                f"(gap: {round(abs(best_val - worst_val), 2)})"
            ),
            "winner_overall": best,
            "strongest_advantage": metric,
            "concern_area": f"{worst} significantly underperforms",
        }

        return json.dumps({
            "success": True,
            "comparison_type": "ranked_comparison",
            "segment_column": col,
            "filters_applied": filters,
            "total_records_analyzed": len(df),
            "segments": segments,
            "comparison": {"metric_used": metric, "total_segments_found": total_segments},
            "summary": summary,
            "metadata": {
                "data_coverage_pct": round(len(df) / self.total_records * 100, 2),
                "execution_note": f"Ranked {total_segments} unique values by {metric}",
            },
        }, default=str)

    def _compare_bank_vs_bank(self, params: Dict) -> str:
        """
        Deep-dive comparison between two banks with breakdowns by txn type and device.

        Args:
            params: Dict with segment_a, segment_b (bank names), filters.

        Returns:
            JSON string with multi-dimensional bank comparison.
        """
        bank_a = params.get("segment_a", "")
        bank_b = params.get("segment_b", "")
        col = data_loader.resolve_column(params.get("segment_column", "sender_bank"))
        metric = params.get("metric", "failure_rate")
        filters = params.get("filters", [])
        include_stats = params.get("include_statistical_tests", True)
        confidence = params.get("confidence_level", 0.95)

        df = self._apply_filters(self.df, filters)
        df_a = df[df[col] == bank_a]
        df_b = df[df[col] == bank_b]

        if df_a.empty or df_b.empty:
            return self._error_response("bank_vs_bank", f"No data for one or both banks", "Check bank names")

        # Overall comparison
        metrics_a = self._compute_segment_metrics(df_a)
        metrics_b = self._compute_segment_metrics(df_b)
        diffs = self._build_difference_block(metrics_a, metrics_b, bank_a, bank_b)

        stat_tests: Dict = {}
        if include_stats:
            stat_tests = self._run_all_statistical_tests(
                df_a, df_b, metrics_a, metrics_b, bank_a, bank_b, confidence,
            )

        # Breakdowns by transaction type
        txn_types = df["transaction_type"].dropna().unique()
        by_txn_type: List[Dict] = []
        for tt in sorted(txn_types):
            ga = df_a[df_a["transaction_type"] == tt]
            gb = df_b[df_b["transaction_type"] == tt]
            if ga.empty and gb.empty:
                continue
            ma = self._compute_segment_metrics(ga) if not ga.empty else self._empty_metrics()
            mb = self._compute_segment_metrics(gb) if not gb.empty else self._empty_metrics()
            primary_a = ma.get(metric, 0)
            primary_b = mb.get(metric, 0)
            lower_better = metric in ("failure_rate", "pending_rate", "fraud_rate", "fraud_by_value_rate")
            winner = bank_a if (primary_a < primary_b if lower_better else primary_a > primary_b) else bank_b
            by_txn_type.append({
                "transaction_type": tt, bank_a: ma, bank_b: mb,
                f"winner_on_{metric}": winner,
            })

        # Breakdown by device type
        devices = df["device_type"].dropna().unique()
        by_device: List[Dict] = []
        for dev in sorted(devices):
            ga = df_a[df_a["device_type"] == dev]
            gb = df_b[df_b["device_type"] == dev]
            if ga.empty and gb.empty:
                continue
            ma = self._compute_segment_metrics(ga) if not ga.empty else self._empty_metrics()
            mb = self._compute_segment_metrics(gb) if not gb.empty else self._empty_metrics()
            primary_a = ma.get(metric, 0)
            primary_b = mb.get(metric, 0)
            lower_better = metric in ("failure_rate", "pending_rate", "fraud_rate", "fraud_by_value_rate")
            winner = bank_a if (primary_a < primary_b if lower_better else primary_a > primary_b) else bank_b
            by_device.append({
                "device_type": dev, bank_a: ma, bank_b: mb,
                f"winner_on_{metric}": winner,
            })

        # Best use case per bank
        best_a = self._find_best_use_case(df_a, metric)
        best_b = self._find_best_use_case(df_b, metric)

        verdict = self._generate_verdict(diffs, bank_a, bank_b, stat_tests)
        summary = self._build_summary(diffs, metrics_a, metrics_b, bank_a, bank_b, metric, stat_tests)

        resp = self._success_response(
            "bank_vs_bank", col, filters, len(df_a) + len(df_b),
            {
                "segment_a": {"label": bank_a, "record_count": len(df_a), "metrics": metrics_a},
                "segment_b": {"label": bank_b, "record_count": len(df_b), "metrics": metrics_b},
            },
            {"differences": diffs, "statistical_tests": stat_tests, "verdict": verdict},
            summary,
        )
        parsed = json.loads(resp)
        parsed["breakdown_by_transaction_type"] = by_txn_type
        parsed["breakdown_by_device_type"] = by_device
        parsed["best_use_case"] = {bank_a: best_a, bank_b: best_b}
        parsed["metadata"]["comparison_side"] = "sender_bank" if col == "sender_bank" else col
        return json.dumps(parsed, default=str)

    def _find_best_use_case(self, bank_df: pd.DataFrame, metric: str) -> Dict:
        """
        Find the transaction_type + device_type combo where a bank performs best.

        Args:
            bank_df: DataFrame for a single bank.
            metric: Metric to optimise.

        Returns:
            Dict with best combo details.
        """
        lower_better = metric in ("failure_rate", "pending_rate", "fraud_rate", "fraud_by_value_rate")
        best_val = float("inf") if lower_better else float("-inf")
        best_combo: Dict = {"transaction_type": "N/A", "device_type": "N/A", "metric_value": 0}

        for (tt, dev), grp in bank_df.groupby(["transaction_type", "device_type"]):
            if len(grp) < 10:  # skip tiny groups
                continue
            m = self._compute_segment_metrics(grp)
            val = m.get(metric, 0)
            if (lower_better and val < best_val) or (not lower_better and val > best_val):
                best_val = val
                best_combo = {"transaction_type": str(tt), "device_type": str(dev), "metric_value": round(val, 2)}

        return best_combo

    def _compare_device_network_matrix(self, params: Dict) -> str:
        """
        Full matrix comparison of device_type × network_type combinations.

        Args:
            params: Dict with metric, filters.

        Returns:
            JSON string with matrix and hotspot detection.
        """
        metric = params.get("metric", "failure_rate")
        filters = params.get("filters", [])

        df = self._apply_filters(self.df, filters)

        devices = sorted(df["device_type"].dropna().unique())
        networks = sorted(df["network_type"].dropna().unique())

        matrix: Dict[str, Dict[str, Any]] = {}
        all_values: List[float] = []

        for dev in devices:
            matrix[dev] = {}
            for net in networks:
                grp = df[(df["device_type"] == dev) & (df["network_type"] == net)]
                m = self._compute_segment_metrics(grp)
                val = m.get(metric, 0)
                matrix[dev][net] = {
                    "value": val,
                    "record_count": len(grp),
                    "full_metrics": m,
                }
                if len(grp) > 0:
                    all_values.append(val)

        # Row and column averages
        row_averages: Dict[str, float] = {}
        for dev in devices:
            vals = [matrix[dev][net]["value"] for net in networks if matrix[dev][net]["record_count"] > 0]
            row_averages[dev] = round(float(np.mean(vals)), 2) if vals else 0.0

        col_averages: Dict[str, float] = {}
        for net in networks:
            vals = [matrix[dev][net]["value"] for dev in devices if matrix[dev][net]["record_count"] > 0]
            col_averages[net] = round(float(np.mean(vals)), 2) if vals else 0.0

        # Find best and worst cells
        lower_better = metric in ("failure_rate", "pending_rate", "fraud_rate", "fraud_by_value_rate")
        best_cell = {"device": "", "network": "", "value": float("inf") if lower_better else float("-inf")}
        worst_cell = {"device": "", "network": "", "value": float("-inf") if lower_better else float("inf")}

        for dev in devices:
            for net in networks:
                cell = matrix[dev][net]
                if cell["record_count"] == 0:
                    continue
                val = cell["value"]
                if lower_better:
                    if val < best_cell["value"]:
                        best_cell = {"device": dev, "network": net, "value": val}
                    if val > worst_cell["value"]:
                        worst_cell = {"device": dev, "network": net, "value": val}
                else:
                    if val > best_cell["value"]:
                        best_cell = {"device": dev, "network": net, "value": val}
                    if val < worst_cell["value"]:
                        worst_cell = {"device": dev, "network": net, "value": val}

        # Hotspot detection (> 1.5 std above mean)
        if all_values:
            mean_val = float(np.mean(all_values))
            std_val = float(np.std(all_values))
            hotspot_threshold = mean_val + 1.5 * std_val
        else:
            mean_val, std_val, hotspot_threshold = 0, 0, float("inf")

        hotspots: List[Dict] = []
        for dev in devices:
            for net in networks:
                cell = matrix[dev][net]
                if cell["record_count"] > 0 and cell["value"] > hotspot_threshold:
                    hotspots.append({
                        "device": dev, "network": net,
                        "value": cell["value"], "record_count": cell["record_count"],
                    })
                    matrix[dev][net]["is_hotspot"] = True
                else:
                    matrix[dev][net]["is_hotspot"] = False

        summary = {
            "key_finding": (
                f"Best: {best_cell['device']}+{best_cell['network']} at {best_cell['value']}% {metric}, "
                f"Worst: {worst_cell['device']}+{worst_cell['network']} at {worst_cell['value']}% {metric}"
            ),
            "winner_overall": f"{best_cell['device']}+{best_cell['network']}",
            "strongest_advantage": f"{metric} = {best_cell['value']}%",
            "concern_area": f"{worst_cell['device']}+{worst_cell['network']} at {worst_cell['value']}%",
        }

        return json.dumps({
            "success": True,
            "comparison_type": "device_network_matrix",
            "segment_column": "device_type × network_type",
            "filters_applied": filters,
            "total_records_analyzed": len(df),
            "matrix": matrix,
            "row_averages": row_averages,
            "column_averages": col_averages,
            "best_cell": best_cell,
            "worst_cell": worst_cell,
            "hotspots": hotspots,
            "hotspot_threshold": round(hotspot_threshold, 2),
            "summary": summary,
            "metadata": {
                "data_coverage_pct": round(len(df) / self.total_records * 100, 2),
                "execution_note": f"Matrix of {len(devices)} devices × {len(networks)} networks",
                "matrix_mean": round(mean_val, 2),
                "matrix_std": round(std_val, 2),
            },
        }, default=str)

    # ------------------------------------------------------------------
    # Response builders
    # ------------------------------------------------------------------

    def _build_summary(
        self,
        diffs: Dict,
        metrics_a: Dict,
        metrics_b: Dict,
        label_a: str,
        label_b: str,
        metric: str,
        stat_tests: Dict,
    ) -> Dict[str, str]:
        """
        Build the summary block with key_finding, winner, strongest advantage, concern.

        Args:
            diffs: Difference block.
            metrics_a, metrics_b: Metric suites.
            label_a, label_b: Segment labels.
            metric: Primary metric name.
            stat_tests: Statistical test results.

        Returns:
            Summary dict.
        """
        # Determine winner
        wins_a = sum(1 for v in diffs.values() if v["winner"] == label_a)
        wins_b = sum(1 for v in diffs.values() if v["winner"] == label_b)
        overall_winner = label_a if wins_a > wins_b else label_b if wins_b > wins_a else "Mixed"

        # Strongest advantage
        strongest_metric = ""
        strongest_pct = 0.0
        for k, v in diffs.items():
            if abs(v["percentage_difference"]) > abs(strongest_pct):
                strongest_pct = v["percentage_difference"]
                strongest_metric = k

        # Concern: a metric where the winner loses
        concern = "None identified"
        for k, v in diffs.items():
            if v["winner"] != overall_winner and v["winner"] != "Tie":
                concern = f"{overall_winner} loses on {k} ({v['segment_a_value']} vs {v['segment_b_value']})"
                break

        # Key finding
        metric_a = metrics_a.get(metric, 0)
        metric_b = metrics_b.get(metric, 0)
        chi_p = stat_tests.get("chi_square", {}).get("p_value")
        sig_str = ""
        if chi_p is not None:
            sig_str = (
                f", statistically significant (p={chi_p})"
                if stat_tests.get("chi_square", {}).get("is_significant")
                else f", not statistically significant (p={chi_p})"
            )
        diff_pct = diffs.get(metric, {}).get("percentage_difference", 0)

        key_finding = (
            f"{label_a} has {metric} of {metric_a} vs {label_b}'s {metric_b} "
            f"({abs(diff_pct):.1f}% difference){sig_str}"
        )

        return {
            "key_finding": key_finding,
            "winner_overall": overall_winner,
            "strongest_advantage": strongest_metric,
            "concern_area": concern,
        }

    def _success_response(
        self,
        comparison_type: str,
        segment_column: str,
        filters_applied: List,
        total_analyzed: int,
        segments: Dict,
        comparison: Dict,
        summary: Dict,
    ) -> str:
        """Build standardised success JSON response."""
        return json.dumps({
            "success": True,
            "comparison_type": comparison_type,
            "segment_column": segment_column,
            "filters_applied": filters_applied,
            "total_records_analyzed": total_analyzed,
            "segments": segments,
            "comparison": comparison,
            "summary": summary,
            "metadata": {
                "data_coverage_pct": round(total_analyzed / self.total_records * 100, 2),
                "execution_note": "Analysis completed successfully",
            },
        }, default=str)

    def _error_response(self, comparison_type: str, error: str, suggestion: str) -> str:
        """Build standardised error JSON response."""
        return json.dumps({
            "success": False,
            "comparison_type": comparison_type,
            "error": error,
            "suggestion": suggestion,
        })


def create_comparison_tool() -> StructuredTool:
    """
    Factory function to create the comparison tool for LangChain.

    Returns:
        StructuredTool configured for segment comparison analysis.
    """
    tool_instance = ComparisonTool()

    return StructuredTool.from_function(
        func=tool_instance.compare,
        name="comparison_tool",
        description=(
            "For ALL segment comparison questions — A vs B, which is better, rank by metric, "
            "cross-segment analysis. Use this for device comparisons, network comparisons, bank "
            "comparisons, age group comparisons, state comparisons, and any 'compare X to Y' question. "
            "Input: comparison_type (string: head_to_head, multi_segment, cross_segment, "
            "metric_comparison, conditional_comparison, ranked_comparison, bank_vs_bank, "
            "device_network_matrix) and parameters (JSON string with segment_column, segment_a, "
            "segment_b, metric, filters, include_statistical_tests, confidence_level, top_n)."
        ),
        args_schema=ComparisonInput,
    )
