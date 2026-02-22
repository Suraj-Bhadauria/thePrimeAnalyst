"""
Trend Tool for PayInsight AI

This module provides comprehensive time-series trend analysis capabilities for
transaction data.  It is the single authoritative handler for all "trend,"
"over time," "increasing / decreasing," "pattern," "trajectory," "movement,"
and "time-series" questions in the system.

Every output includes both raw and SMA-smoothed values, a trend classification
block (direction, shape, momentum), peak / trough identification, an optional
linear forecast, and a rich summary narrative suitable for the InsightAgent.

Supported trend types:
    hourly_trend, daily_trend, date_trend, multi_metric_trend, segmented_trend,
    rolling_anomaly_trend, acceleration_trend, comparative_period_trend,
    cumulative_trend, volatility_trend.

Author: Team primeFactors
"""

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
import pandas as pd
import numpy as np
import json
import math
from typing import Any, Dict, List, Optional, Tuple
from src.utils.data_loader import data_loader


# ---------------------------------------------------------------------------
# Input schema
# ---------------------------------------------------------------------------

class TrendInput(BaseModel):
    """Input schema for the trend tool."""

    trend_type: str = Field(
        description=(
            "Type of trend analysis: hourly_trend, daily_trend, date_trend, "
            "multi_metric_trend, segmented_trend, rolling_anomaly_trend, "
            "acceleration_trend, comparative_period_trend, cumulative_trend, "
            "volatility_trend"
        )
    )
    parameters: str = Field(
        description=(
            "JSON string with: metric (volume, failure_rate, success_rate, "
            "fraud_rate, avg_amount, total_amount, pending_rate, fraud_by_value_rate), "
            "time_granularity (hour, day_of_week, date), smoothing_window (int), "
            "smoothing_method (sma, ema, centered), filters (list), "
            "secondary_metrics (list), segment_column (string), segment_values (list), "
            "trend_window_start (int), trend_window_end (int), min_data_points (int), "
            "include_forecast (bool), period_a_filter (list), period_b_filter (list), "
            "period_a_label (string), period_b_label (string)"
        )
    )


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_TREND_TYPES = {
    "hourly_trend",
    "daily_trend",
    "date_trend",
    "multi_metric_trend",
    "segmented_trend",
    "rolling_anomaly_trend",
    "acceleration_trend",
    "comparative_period_trend",
    "cumulative_trend",
    "volatility_trend",
}

VALID_METRICS = {
    "volume",
    "failure_rate",
    "success_rate",
    "fraud_rate",
    "avg_amount",
    "total_amount",
    "pending_rate",
    "fraud_by_value_rate",
}

PERIOD_LABELS: Dict[int, str] = {
    **{h: "Late Night" for h in range(0, 6)},
    **{h: "Morning" for h in range(6, 12)},
    **{h: "Afternoon" for h in range(12, 18)},
    **{h: "Evening Peak" for h in range(18, 22)},
    **{h: "Night" for h in range(22, 24)},
}

DAY_NAMES: Dict[int, str] = {
    0: "Monday",
    1: "Tuesday",
    2: "Wednesday",
    3: "Thursday",
    4: "Friday",
    5: "Saturday",
    6: "Sunday",
}


def _hour_label(h: int) -> str:
    """Return a human-readable label for an hour integer (0–23)."""
    suffix = "AM" if h < 12 else "PM"
    display = h if h <= 12 else h - 12
    if display == 0:
        display = 12
    return f"{display} {suffix}"


def _safe_round(val: Any, decimals: int = 2) -> Any:
    """Round a value if it is numeric; pass through otherwise."""
    if val is None or (isinstance(val, float) and (math.isnan(val) or math.isinf(val))):
        return None
    try:
        return round(float(val), decimals)
    except (TypeError, ValueError):
        return val


# ---------------------------------------------------------------------------
# Main tool class
# ---------------------------------------------------------------------------

class TrendTool:
    """
    Comprehensive time-series trend analysis tool for transaction data.

    Computes raw and smoothed (SMA / EMA / centered) metric series across
    hours, days of week, or calendar dates.  Supports 10 trend analysis modes
    including segmented overlays, anomaly bands, acceleration, cumulative
    totals, volatility tracking, and comparative period analysis.

    Attributes:
        df: Full transaction DataFrame from the singleton data_loader.
        total_records: Row count of the full dataset.
    """

    def __init__(self) -> None:
        """Initialize TrendTool with data from the singleton loader."""
        self.df: pd.DataFrame = data_loader.load_data()
        self.total_records: int = len(self.df)

    # ==================================================================
    # Public entry point
    # ==================================================================

    def analyze(self, trend_type: str, parameters: str) -> str:
        """
        Main entry point for trend analysis.

        Args:
            trend_type: One of the 10 supported trend analysis modes.
            parameters: JSON string with metric, time_granularity, smoothing,
                        filters, and mode-specific options.

        Returns:
            JSON string with the complete trend analysis result.
        """
        try:
            params: Dict = json.loads(parameters) if parameters else {}
        except json.JSONDecodeError as exc:
            return self._error_response(
                trend_type,
                f"Invalid JSON in parameters: {exc}",
                "Ensure parameters is a valid JSON string.",
            )

        if trend_type not in VALID_TREND_TYPES:
            return self._error_response(
                trend_type,
                f"Unknown trend_type: {trend_type}",
                f"Valid types: {', '.join(sorted(VALID_TREND_TYPES))}",
            )

        dispatch: Dict[str, Any] = {
            "hourly_trend": self._hourly_trend,
            "daily_trend": self._daily_trend,
            "date_trend": self._date_trend,
            "multi_metric_trend": self._multi_metric_trend,
            "segmented_trend": self._segmented_trend,
            "rolling_anomaly_trend": self._rolling_anomaly_trend,
            "acceleration_trend": self._acceleration_trend,
            "comparative_period_trend": self._comparative_period_trend,
            "cumulative_trend": self._cumulative_trend,
            "volatility_trend": self._volatility_trend,
        }

        try:
            return dispatch[trend_type](params)
        except Exception as exc:
            return self._error_response(
                trend_type,
                f"Trend analysis failed: {exc}",
                "Check your parameters and try again.",
            )

    # ==================================================================
    # Internal helpers — filters & metric computation
    # ==================================================================

    def _apply_filters(self, df: pd.DataFrame, filters: List[Dict]) -> pd.DataFrame:
        """
        Apply a list of filter conditions to *df* and return the subset.

        Args:
            df: DataFrame to filter.
            filters: List of dicts with keys column, operator, value.

        Returns:
            Filtered DataFrame.
        """
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
                df = df[df[col] > float(val)]
            elif op == ">=":
                df = df[df[col] >= float(val)]
            elif op == "<":
                df = df[df[col] < float(val)]
            elif op == "<=":
                df = df[df[col] <= float(val)]
            elif op == "in":
                df = df[df[col].isin(val if isinstance(val, list) else [val])]
            elif op == "not_in":
                df = df[~df[col].isin(val if isinstance(val, list) else [val])]
        return df

    def _compute_metric_series(
        self,
        df: pd.DataFrame,
        group_col: str,
        metric: str,
    ) -> pd.Series:
        """
        Compute a single metric aggregated by *group_col*.

        Args:
            df: DataFrame (already filtered).
            group_col: Column to group by (e.g. 'hour_of_day').
            metric: One of the VALID_METRICS strings.

        Returns:
            pd.Series indexed by group_col values with computed metric.
        """
        if metric == "volume":
            return df.groupby(group_col).size()
        elif metric == "total_amount":
            return df.groupby(group_col)["amount_inr"].sum()
        elif metric == "avg_amount":
            return df.groupby(group_col)["amount_inr"].mean()
        elif metric == "failure_rate":
            g = df.groupby(group_col)
            return (g["transaction_status"].apply(lambda s: (s == "FAILED").mean()) * 100)
        elif metric == "success_rate":
            g = df.groupby(group_col)
            return (g["transaction_status"].apply(lambda s: (s == "SUCCESS").mean()) * 100)
        elif metric == "pending_rate":
            g = df.groupby(group_col)
            return (g["transaction_status"].apply(lambda s: (s == "PENDING").mean()) * 100)
        elif metric == "fraud_rate":
            g = df.groupby(group_col)
            return (g["fraud_flag"].mean() * 100)
        elif metric == "fraud_by_value_rate":
            def _fraud_value_pct(sub: pd.DataFrame) -> float:
                total = sub["amount_inr"].sum()
                if total == 0:
                    return 0.0
                return (sub.loc[sub["fraud_flag"] == True, "amount_inr"].sum() / total) * 100
            return df.groupby(group_col).apply(_fraud_value_pct)
        else:
            return df.groupby(group_col).size()

    # ==================================================================
    # Smoothing helpers
    # ==================================================================

    def _apply_smoothing(
        self,
        series: pd.Series,
        window: int,
        method: str = "sma",
    ) -> Tuple[pd.Series, int, bool]:
        """
        Apply rolling smoothing to a numeric series.

        Args:
            series: Raw metric values (sorted by time axis).
            window: Requested smoothing window size.
            method: One of 'sma', 'ema', 'centered'.

        Returns:
            Tuple of (smoothed_series, actual_window_used, was_adjusted).
        """
        n = len(series)
        adjusted = False

        if window > n:
            window = max(2, n // 2) if n >= 4 else max(1, n)
            adjusted = True

        if method == "ema":
            smoothed = series.ewm(span=window, min_periods=1, adjust=False).mean()
        elif method == "centered":
            smoothed = series.rolling(window=window, min_periods=1, center=True).mean()
        else:  # default sma
            smoothed = series.rolling(window=window, min_periods=1).mean()

        return smoothed, window, adjusted

    # ==================================================================
    # Trend classification helpers
    # ==================================================================

    def _classify_trend_direction(
        self, sma_values: pd.Series,
    ) -> Dict[str, Any]:
        """
        Classify the overall trend direction from SMA-smoothed values.

        Compares the mean of the first third to the mean of the last third.

        Args:
            sma_values: SMA-smoothed series ordered by time.

        Returns:
            Dict with direction, pct_change, early_avg, late_avg.
        """
        n = len(sma_values)
        if n < 3:
            return {
                "direction": "Insufficient Data",
                "pct_change_early_to_late": 0.0,
                "early_period_avg": _safe_round(sma_values.mean()),
                "late_period_avg": _safe_round(sma_values.mean()),
            }
        third = max(1, n // 3)
        early_avg = float(sma_values.iloc[:third].mean())
        late_avg = float(sma_values.iloc[-third:].mean())
        if early_avg == 0:
            pct = 0.0
        else:
            pct = ((late_avg - early_avg) / abs(early_avg)) * 100

        if pct > 15:
            direction = "Strong Upward"
        elif pct > 5:
            direction = "Moderate Upward"
        elif pct > 1:
            direction = "Slight Upward"
        elif pct >= -1:
            direction = "Stable"
        elif pct >= -5:
            direction = "Slight Downward"
        elif pct >= -15:
            direction = "Moderate Downward"
        else:
            direction = "Strong Downward"

        return {
            "direction": direction,
            "pct_change_early_to_late": _safe_round(pct),
            "early_period_avg": _safe_round(early_avg),
            "late_period_avg": _safe_round(late_avg),
        }

    def _classify_trend_shape(self, sma_values: pd.Series) -> str:
        """
        Classify the overall shape of the SMA-smoothed series.

        Args:
            sma_values: SMA-smoothed series ordered by time.

        Returns:
            One of: Consistently Rising, Consistently Falling, Inverted U / Peak,
            U-Shaped / Valley, Oscillating, Irregular.
        """
        n = len(sma_values)
        if n < 3:
            return "Insufficient Data"

        diffs = sma_values.diff().dropna()
        pos = (diffs > 0).sum()
        neg = (diffs < 0).sum()

        # Monotonic checks (allow one deviation)
        if pos >= n - 2 and neg <= 1:
            return "Consistently Rising"
        if neg >= n - 2 and pos <= 1:
            return "Consistently Falling"

        # Peak / valley — locate argmax / argmin relative position
        peak_idx = int(sma_values.values.argmax())
        trough_idx = int(sma_values.values.argmin())
        mid_low = n * 0.25
        mid_high = n * 0.75

        if mid_low <= peak_idx <= mid_high and (trough_idx < mid_low or trough_idx > mid_high):
            return "Inverted U / Peak"
        if mid_low <= trough_idx <= mid_high and (peak_idx < mid_low or peak_idx > mid_high):
            return "U-Shaped / Valley"

        # Oscillating — count sign changes in diffs
        sign_changes = ((diffs.values[:-1] * diffs.values[1:]) < 0).sum()
        if sign_changes >= n * 0.4:
            return "Oscillating"

        return "Irregular"

    def _classify_momentum(self, sma_values: pd.Series) -> str:
        """
        Classify momentum: Accelerating, Decelerating, or Steady.

        Args:
            sma_values: SMA-smoothed series ordered by time.

        Returns:
            Momentum label string.
        """
        n = len(sma_values)
        if n < 4:
            return "Steady"
        first_deriv = sma_values.diff().dropna()
        second_deriv = first_deriv.diff().dropna()
        mean_accel = float(second_deriv.mean())
        abs_first = float(first_deriv.abs().mean())
        if abs_first == 0:
            return "Steady"
        ratio = abs(mean_accel) / abs_first
        if ratio < 0.15:
            return "Steady"
        if mean_accel > 0:
            return "Accelerating"
        return "Decelerating"

    # ==================================================================
    # Peak / trough & local extrema
    # ==================================================================

    def _find_peak_trough(
        self,
        time_labels: List[str],
        raw_values: List[float],
    ) -> Dict[str, Any]:
        """
        Identify the global peak and trough in the raw series.

        Args:
            time_labels: Human-readable labels per time point.
            raw_values: Raw metric values per time point.

        Returns:
            Dict with peak/trough details and volatility label.
        """
        arr = np.array(raw_values, dtype=float)
        peak_idx = int(np.nanargmax(arr))
        trough_idx = int(np.nanargmin(arr))
        peak_val = float(arr[peak_idx])
        trough_val = float(arr[trough_idx])
        rng = peak_val - trough_val
        mean_val = float(np.nanmean(arr))
        if mean_val == 0:
            pct_range = 0.0
        else:
            pct_range = (rng / abs(mean_val)) * 100

        if pct_range > 50:
            label = "High Volatility"
        elif pct_range > 20:
            label = "Moderate Volatility"
        else:
            label = "Low Volatility"

        return {
            "peak_time_point": time_labels[peak_idx],
            "peak_raw_value": _safe_round(peak_val),
            "trough_time_point": time_labels[trough_idx],
            "trough_raw_value": _safe_round(trough_val),
            "peak_to_trough_range": _safe_round(rng),
            "peak_to_trough_pct": _safe_round(pct_range),
            "peak_to_trough_label": label,
        }

    def _detect_local_extrema(
        self, raw_values: List[float],
    ) -> Tuple[List[bool], List[bool]]:
        """
        Detect local peaks and troughs in the raw series.

        Args:
            raw_values: Raw metric values per time point.

        Returns:
            Tuple of (is_local_peak list, is_local_trough list).
        """
        n = len(raw_values)
        peaks = [False] * n
        troughs = [False] * n
        for i in range(1, n - 1):
            if raw_values[i] > raw_values[i - 1] and raw_values[i] > raw_values[i + 1]:
                peaks[i] = True
            if raw_values[i] < raw_values[i - 1] and raw_values[i] < raw_values[i + 1]:
                troughs[i] = True
        return peaks, troughs

    # ==================================================================
    # Forecast helper
    # ==================================================================

    def _compute_forecast(
        self,
        sma_values: pd.Series,
        time_points: List[Any],
        n_forecast: int = 3,
    ) -> Dict[str, Any]:
        """
        Simple linear extrapolation of the SMA trend.

        Uses the slope of the last 5 SMA points (or all if fewer) to project
        the next *n_forecast* time points.

        Args:
            sma_values: SMA-smoothed series ordered by time.
            time_points: Raw time point values (ints or date strings).
            n_forecast: Number of future points to project.

        Returns:
            Dict with forecast points and confidence note.
        """
        n = len(sma_values)
        tail = min(5, n)
        y = sma_values.values[-tail:]
        x = np.arange(tail, dtype=float)
        if tail < 2:
            return {"included": False, "next_3_points": [], "forecast_method": "linear_extrapolation",
                    "confidence_note": "Insufficient data for forecast"}
        slope = float(np.polyfit(x, y, 1)[0])
        last_val = float(y[-1])
        points = []
        for i in range(1, n_forecast + 1):
            forecast_val = _safe_round(last_val + slope * i)
            points.append({
                "step_ahead": i,
                "forecast_value": forecast_val,
            })
        return {
            "included": True,
            "next_3_points": points,
            "forecast_method": "linear_extrapolation",
            "confidence_note": (
                "Linear extrapolation based on the last 5 SMA-smoothed data points. "
                "This is a simple projection — actual values may differ due to non-linear "
                "patterns, external factors, or cyclical behavior."
            ),
        }

    # ==================================================================
    # Missing time points fill
    # ==================================================================

    def _fill_missing_time_points(
        self,
        series: pd.Series,
        granularity: str,
        metric: str,
        df: pd.DataFrame,
    ) -> Tuple[pd.Series, int]:
        """
        Ensure all expected time points are present in the series.

        For hour: 0–23.  For day_of_week: 0–6.  For date: all unique dates
        in the DataFrame.

        Fills missing volume-type metrics with 0 and rate metrics with the
        global average for that time point (falls back to 0 if unavailable).

        Args:
            series: Metric series indexed by time point.
            granularity: 'hour', 'day_of_week', or 'date'.
            metric: The metric name being computed.
            df: The (filtered) DataFrame used to compute global averages.

        Returns:
            Tuple of (filled series, count of missing points filled).
        """
        if granularity == "hour":
            full_idx = pd.RangeIndex(0, 24)
        elif granularity == "day_of_week":
            full_idx = pd.RangeIndex(0, 7)
        else:
            return series, 0  # date granularity — no forced fill

        missing = full_idx.difference(series.index)
        n_filled = len(missing)
        if n_filled == 0:
            return series, 0

        rate_metrics = {"failure_rate", "success_rate", "fraud_rate", "pending_rate",
                        "avg_amount", "fraud_by_value_rate"}
        if metric in rate_metrics:
            # Use 0 for rate fills (safe for SMA since min_periods=1 handles gracefully)
            fill_val = 0.0
        else:
            fill_val = 0

        series = series.reindex(full_idx, fill_value=fill_val)
        return series.sort_index(), n_filled

    # ==================================================================
    # Derivative helpers
    # ==================================================================

    def _compute_first_derivative(self, series: pd.Series) -> pd.Series:
        """
        Compute rate of change (velocity) between consecutive values.

        Args:
            series: Numeric series ordered by time.

        Returns:
            Series of same length with NaN at position 0.
        """
        return series.diff()

    def _compute_second_derivative(self, series: pd.Series) -> pd.Series:
        """
        Compute acceleration (change in velocity) between consecutive values.

        Args:
            series: First derivative series.

        Returns:
            Series of same length with NaN at positions 0–1.
        """
        return series.diff()

    # ==================================================================
    # Summary narrative builder
    # ==================================================================

    def _build_summary_narrative(
        self,
        metric: str,
        direction_info: Dict[str, Any],
        shape: str,
        momentum: str,
        peak_trough: Dict[str, Any],
        granularity: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """
        Build the complete summary block consumed by the InsightAgent.

        Args:
            metric: Metric name analysed.
            direction_info: Output of _classify_trend_direction.
            shape: Trend shape label.
            momentum: Trend momentum label.
            peak_trough: Output of _find_peak_trough.
            granularity: Time granularity used.
            extra: Optional dict with additional context-specific info.

        Returns:
            Dict with key_finding, trend_narrative, peak_statement,
            trough_statement, direction_statement, business_implication.
        """
        direction = direction_info["direction"]
        pct = direction_info["pct_change_early_to_late"]
        early = direction_info["early_period_avg"]
        late = direction_info["late_period_avg"]
        peak_tp = peak_trough["peak_time_point"]
        peak_val = peak_trough["peak_raw_value"]
        trough_tp = peak_trough["trough_time_point"]
        trough_val = peak_trough["trough_raw_value"]

        metric_label = metric.replace("_", " ").title()
        gran_label = {"hour": "across the day (hours 0–23)", "day_of_week": "across the week (Monday–Sunday)", "date": "across calendar dates"}.get(granularity, granularity)

        # --- key_finding ---
        key_finding = (
            f"{metric_label} follows a {direction} trend {gran_label}, "
            f"moving from {early} in the early period to {late} in the late period "
            f"— a {abs(pct)}% {'increase' if pct >= 0 else 'decrease'}."
        )

        # --- trend_narrative ---
        narrative_parts = [
            f"The {metric_label} series {gran_label} exhibits a {shape} pattern "
            f"with {momentum.lower()} momentum.",
            f"The peak occurs at {peak_tp} ({peak_val}) and the trough at {trough_tp} ({trough_val}).",
        ]
        if abs(pct) > 5:
            narrative_parts.append(
                f"SMA smoothing reveals a clear {direction.lower()} directional movement "
                f"that may not be immediately visible in the noisy raw data."
            )
        else:
            narrative_parts.append(
                "Both the raw and SMA-smoothed series tell a consistent story — "
                "the metric remains relatively stable with minor fluctuations."
            )
        trend_narrative = " ".join(narrative_parts)

        # --- peak_statement ---
        peak_statement = (
            f"{metric_label} peaks at {peak_tp} with a value of {peak_val} — "
            f"the highest point in the series."
        )

        # --- trough_statement ---
        trough_statement = (
            f"{metric_label} reaches its minimum at {trough_tp} with a value of {trough_val} — "
            f"the lowest point in the series."
        )

        # --- direction_statement ---
        direction_statement = (
            f"Overall the series shows a {direction} trend with a "
            f"{abs(pct)}% {'increase' if pct >= 0 else 'decrease'} from the early period "
            f"average ({early}) to the late period average ({late}) based on SMA-smoothed values."
        )

        # --- business_implication ---
        implication_map: Dict[str, Dict[str, str]] = {
            "failure_rate": {
                "up": f"The rising failure rate toward {peak_tp} suggests server capacity or network infrastructure should be scaled during that window to reduce transaction failures.",
                "down": f"Failure rate declining toward {trough_tp} indicates improving reliability — maintain current infrastructure investments in that period.",
                "stable": "Failure rate is stable across the time axis — no immediate infrastructure rebalancing needed, but monitor for emerging patterns.",
            },
            "volume": {
                "up": f"Transaction volume concentrating around {peak_tp} means staffing, server auto-scaling, and fraud monitoring should be front-loaded for that period.",
                "down": f"Declining volume toward {trough_tp} presents an opportunity for scheduled maintenance or batch processing during low-traffic windows.",
                "stable": "Consistent volume distribution suggests steady demand — resource allocation can remain uniform.",
            },
            "fraud_rate": {
                "up": f"The upward fraud rate trend peaking at {peak_tp} demands heightened real-time monitoring and stricter authentication rules during that window.",
                "down": f"Fraud rate declining toward {trough_tp} suggests existing controls are effective — consider relaxing friction in low-risk periods to improve UX.",
                "stable": "Stable fraud rate across the time axis indicates consistent risk exposure — maintain current detection thresholds.",
            },
            "avg_amount": {
                "up": f"Rising average transaction value peaking at {peak_tp} may indicate higher-value use cases dominating during that time — adjust risk scoring thresholds accordingly.",
                "down": f"Decreasing average amount toward {trough_tp} suggests a shift to micro-transactions — ensure processing fees remain viable.",
                "stable": "Stable average amount across the time axis implies consistent transaction behavior — no repricing action needed.",
            },
        }

        direction_key = "up" if pct > 1 else ("down" if pct < -1 else "stable")
        metric_impl = implication_map.get(metric, {})
        business_implication = metric_impl.get(
            direction_key,
            f"The {direction.lower()} trend in {metric_label} peaking at {peak_tp} should be reviewed by the operations team to determine resource allocation adjustments.",
        )

        return {
            "key_finding": key_finding,
            "trend_narrative": trend_narrative,
            "peak_statement": peak_statement,
            "trough_statement": trough_statement,
            "direction_statement": direction_statement,
            "business_implication": business_implication,
        }

    # ==================================================================
    # Standard time-series record builder
    # ==================================================================

    def _build_time_series_records(
        self,
        time_points: List[Any],
        time_labels: List[str],
        raw_values: np.ndarray,
        sma_values: np.ndarray,
        smoothing_window: int,
        granularity: str,
    ) -> List[Dict[str, Any]]:
        """
        Build the standard per-time-point record list.

        Args:
            time_points: Raw time point values.
            time_labels: Human-readable labels.
            raw_values: Raw metric values (np array).
            sma_values: SMA-smoothed values (np array).
            smoothing_window: Window size used for smoothing.
            granularity: Time granularity for extra annotations.

        Returns:
            List of dicts, one per time point, following the standard schema.
        """
        n = len(time_points)
        series_mean = float(np.nanmean(raw_values))
        local_peaks, local_troughs = self._detect_local_extrema(raw_values.tolist())

        # Ranks (1 = highest)
        temp = pd.Series(raw_values)
        ranks = temp.rank(ascending=False, method="min").astype(int).tolist()

        half_w = smoothing_window // 2
        records: List[Dict[str, Any]] = []
        for i in range(n):
            rv = float(raw_values[i]) if not np.isnan(raw_values[i]) else None
            sv = float(sma_values[i]) if not np.isnan(sma_values[i]) else None

            change_prev = None
            pct_change_prev = None
            sma_change_prev = None
            if i > 0:
                prev_rv = float(raw_values[i - 1])
                if rv is not None and not np.isnan(prev_rv):
                    change_prev = _safe_round(rv - prev_rv)
                    if prev_rv != 0:
                        pct_change_prev = _safe_round(((rv - prev_rv) / abs(prev_rv)) * 100)
                prev_sv = float(sma_values[i - 1])
                if sv is not None and not np.isnan(prev_sv):
                    sma_change_prev = _safe_round(sv - prev_sv)

            vs_avg = _safe_round(rv - series_mean) if rv is not None else None
            vs_avg_pct = _safe_round(((rv - series_mean) / abs(series_mean)) * 100) if (rv is not None and series_mean != 0) else None

            rec: Dict[str, Any] = {
                "time_point": time_points[i],
                "time_label": time_labels[i],
                "is_edge_point": (i < half_w) or (i >= n - half_w),
                "raw_value": _safe_round(rv),
                "raw_rank": ranks[i],
                "sma_value": _safe_round(sv),
                "sma_window_used": min(smoothing_window, i + 1) if i < smoothing_window else smoothing_window,
                "change_from_previous": change_prev,
                "pct_change_from_previous": pct_change_prev,
                "sma_change_from_previous": sma_change_prev,
                "vs_series_average": vs_avg,
                "vs_series_average_pct": vs_avg_pct,
                "is_above_average": rv > series_mean if rv is not None else None,
                "is_local_peak": local_peaks[i],
                "is_local_trough": local_troughs[i],
            }

            # Extra annotations per granularity
            if granularity == "hour":
                rec["period_label"] = PERIOD_LABELS.get(time_points[i], "Unknown")
                rec["is_peak_hour"] = 18 <= time_points[i] <= 21
            elif granularity == "day_of_week":
                rec["is_weekend"] = time_points[i] in (5, 6)

            records.append(rec)
        return records

    # ==================================================================
    # Error / success response helpers
    # ==================================================================

    def _error_response(self, trend_type: str, error: str, suggestion: str) -> str:
        """Return a standardised error JSON string."""
        return json.dumps({
            "success": False,
            "trend_type": trend_type,
            "error": error,
            "suggestion": suggestion,
        })

    def _wrap_response(
        self,
        trend_type: str,
        metric: str,
        granularity: str,
        smoothing_method: str,
        smoothing_window: int,
        filters: List[Dict],
        total_records: int,
        time_series: List[Dict],
        trend_classification: Dict,
        peak_trough: Dict,
        summary: Dict,
        forecast: Optional[Dict] = None,
        window_adjusted: bool = False,
        original_window: int = 3,
        missing_filled: int = 0,
        extra: Optional[Dict] = None,
    ) -> str:
        """
        Build the standard success JSON wrapper.

        Args:
            All components of the response.

        Returns:
            JSON string with the full trend analysis result.
        """
        data_coverage = 100.0 if self.total_records == 0 else round((total_records / self.total_records) * 100, 2)
        result: Dict[str, Any] = {
            "success": True,
            "trend_type": trend_type,
            "metric": metric,
            "time_granularity": granularity,
            "smoothing_method": smoothing_method,
            "smoothing_window": smoothing_window,
            "filters_applied": filters,
            "total_records_analyzed": total_records,
            "time_points_in_series": len(time_series),
            "time_series": time_series,
            "trend_classification": trend_classification,
            "peak_trough": peak_trough,
            "forecast": forecast or {"included": False, "next_3_points": [], "forecast_method": "linear_extrapolation", "confidence_note": "Forecast not requested."},
            "summary": summary,
            "metadata": {
                "smoothing_window_adjusted": window_adjusted,
                "original_requested_window": original_window,
                "actual_window_used": smoothing_window,
                "missing_time_points_filled": missing_filled,
                "data_coverage_pct": data_coverage,
                "execution_note": "Smoothing window was reduced to fit available data points." if window_adjusted else "None",
            },
        }
        if extra:
            result.update(extra)
        return json.dumps(result, default=str)

    # ==================================================================
    # Core single-metric trend builder (reused by multiple trend types)
    # ==================================================================

    def _build_single_metric_trend(
        self,
        df: pd.DataFrame,
        metric: str,
        granularity: str,
        smoothing_window: int,
        smoothing_method: str,
        trend_window_start: Optional[int],
        trend_window_end: Optional[int],
        min_data_points: int,
    ) -> Dict[str, Any]:
        """
        Core computation: metric series → smoothed → classified → records.

        Args:
            df: Filtered DataFrame.
            metric: Metric to compute.
            granularity: Time granularity.
            smoothing_window: Requested window.
            smoothing_method: sma / ema / centered.
            trend_window_start: Optional start of time range.
            trend_window_end: Optional end of time range.
            min_data_points: Minimum points required.

        Returns:
            Dict with keys: raw_series, sma_series, time_points, time_labels,
            records, direction_info, shape, momentum, peak_trough, summary,
            smoothing_window, window_adjusted, missing_filled, total_records.
        """
        group_col = {
            "hour": "hour_of_day",
            "day_of_week": "day_of_week",
            "date": "_date",
        }[granularity]

        # Prepare date column if needed
        working_df = df.copy()
        if granularity == "date":
            working_df["_date"] = working_df["timestamp"].dt.date

        raw_series = self._compute_metric_series(working_df, group_col, metric)

        # Fill missing time points
        missing_filled = 0
        if granularity in ("hour", "day_of_week"):
            raw_series, missing_filled = self._fill_missing_time_points(
                raw_series, granularity, metric, working_df,
            )

        raw_series = raw_series.sort_index()

        # Apply time window filter
        if trend_window_start is not None or trend_window_end is not None:
            idx = raw_series.index
            if granularity != "date":
                mask = pd.Series(True, index=idx)
                if trend_window_start is not None:
                    mask &= idx >= trend_window_start
                if trend_window_end is not None:
                    mask &= idx <= trend_window_end
                raw_series = raw_series[mask]

        if len(raw_series) < min_data_points:
            raise ValueError(
                f"Only {len(raw_series)} time points after filtering — "
                f"minimum required is {min_data_points}."
            )

        original_window = smoothing_window
        sma_series, smoothing_window, window_adjusted = self._apply_smoothing(
            raw_series, smoothing_window, smoothing_method,
        )

        # Build labels
        if granularity == "hour":
            time_points = raw_series.index.tolist()
            time_labels = [_hour_label(h) for h in time_points]
        elif granularity == "day_of_week":
            time_points = raw_series.index.tolist()
            time_labels = [DAY_NAMES.get(d, str(d)) for d in time_points]
        else:
            time_points = [str(d) for d in raw_series.index.tolist()]
            time_labels = time_points

        raw_arr = raw_series.values.astype(float)
        sma_arr = sma_series.values.astype(float)

        records = self._build_time_series_records(
            time_points, time_labels, raw_arr, sma_arr, smoothing_window, granularity,
        )

        direction_info = self._classify_trend_direction(sma_series)
        shape = self._classify_trend_shape(sma_series)
        momentum = self._classify_momentum(sma_series)
        peak_trough = self._find_peak_trough(time_labels, raw_arr.tolist())

        trend_classification = {
            **direction_info,
            "shape": shape,
            "momentum": momentum,
        }

        summary = self._build_summary_narrative(
            metric, direction_info, shape, momentum, peak_trough, granularity,
        )

        return {
            "raw_series": raw_series,
            "sma_series": sma_series,
            "time_points": time_points,
            "time_labels": time_labels,
            "raw_arr": raw_arr,
            "sma_arr": sma_arr,
            "records": records,
            "direction_info": direction_info,
            "shape": shape,
            "momentum": momentum,
            "peak_trough": peak_trough,
            "trend_classification": trend_classification,
            "summary": summary,
            "smoothing_window": smoothing_window,
            "window_adjusted": window_adjusted,
            "original_window": original_window,
            "missing_filled": missing_filled,
            "total_records": len(df),
        }

    # ==================================================================
    # Trend type implementations
    # ==================================================================

    def _hourly_trend(self, params: Dict) -> str:
        """
        24-hour cycle analysis for a chosen metric.

        Args:
            params: Parameters dict with metric, smoothing, filters, etc.

        Returns:
            JSON string with hourly trend results.
        """
        metric = params.get("metric", "volume")
        smoothing_window = min(params.get("smoothing_window", 3), 6)
        smoothing_method = params.get("smoothing_method", "sma")
        filters = params.get("filters", [])
        include_forecast = params.get("include_forecast", False)
        min_dp = params.get("min_data_points", 3)
        tw_start = params.get("trend_window_start")
        tw_end = params.get("trend_window_end")

        df = self._apply_filters(self.df.copy(), filters)

        result = self._build_single_metric_trend(
            df, metric, "hour", smoothing_window, smoothing_method,
            tw_start, tw_end, min_dp,
        )

        # Extra hourly fields
        records = result["records"]
        morning_vals = [r["raw_value"] for r in records if r["time_point"] in range(6, 12) and r["raw_value"] is not None]
        evening_vals = [r["raw_value"] for r in records if r["time_point"] in range(18, 22) and r["raw_value"] is not None]
        morning_avg = _safe_round(np.mean(morning_vals)) if morning_vals else None
        evening_avg = _safe_round(np.mean(evening_vals)) if evening_vals else None
        morning_to_evening_change = _safe_round(evening_avg - morning_avg) if (morning_avg is not None and evening_avg is not None) else None

        sma_arr = result["sma_arr"]
        daily_cycle_amplitude = _safe_round(float(np.nanmax(sma_arr) - np.nanmin(sma_arr)))

        forecast = None
        if include_forecast:
            forecast = self._compute_forecast(result["sma_series"], result["time_points"])

        extra = {
            "hourly_extras": {
                "morning_avg_6_to_11": morning_avg,
                "evening_avg_18_to_21": evening_avg,
                "morning_to_evening_change": morning_to_evening_change,
                "daily_cycle_amplitude": daily_cycle_amplitude,
            }
        }

        return self._wrap_response(
            trend_type="hourly_trend",
            metric=metric,
            granularity="hour",
            smoothing_method=smoothing_method,
            smoothing_window=result["smoothing_window"],
            filters=filters,
            total_records=result["total_records"],
            time_series=result["records"],
            trend_classification=result["trend_classification"],
            peak_trough=result["peak_trough"],
            summary=result["summary"],
            forecast=forecast,
            window_adjusted=result["window_adjusted"],
            original_window=result["original_window"],
            missing_filled=result["missing_filled"],
            extra=extra,
        )

    def _daily_trend(self, params: Dict) -> str:
        """
        Seven-day weekly cycle analysis.

        Args:
            params: Parameters dict with metric, smoothing, filters, etc.

        Returns:
            JSON string with daily trend results.
        """
        metric = params.get("metric", "volume")
        smoothing_window = min(params.get("smoothing_window", 3), 3)  # max 3 for 7 points
        smoothing_method = params.get("smoothing_method", "sma")
        filters = params.get("filters", [])
        include_forecast = params.get("include_forecast", False)
        min_dp = params.get("min_data_points", 3)

        df = self._apply_filters(self.df.copy(), filters)

        result = self._build_single_metric_trend(
            df, metric, "day_of_week", smoothing_window, smoothing_method,
            None, None, min_dp,
        )

        records = result["records"]
        weekday_vals = [r["raw_value"] for r in records if r["time_point"] in range(0, 5) and r["raw_value"] is not None]
        weekend_vals = [r["raw_value"] for r in records if r["time_point"] in (5, 6) and r["raw_value"] is not None]
        weekday_avg = _safe_round(np.mean(weekday_vals)) if weekday_vals else None
        weekend_avg = _safe_round(np.mean(weekend_vals)) if weekend_vals else None
        delta_abs = _safe_round(weekend_avg - weekday_avg) if (weekday_avg is not None and weekend_avg is not None) else None
        delta_pct = _safe_round(((weekend_avg - weekday_avg) / abs(weekday_avg)) * 100) if (weekday_avg and weekday_avg != 0) else None

        forecast = None
        if include_forecast:
            forecast = self._compute_forecast(result["sma_series"], result["time_points"])

        extra = {
            "daily_extras": {
                "weekday_average": weekday_avg,
                "weekend_average": weekend_avg,
                "weekend_vs_weekday_delta_abs": delta_abs,
                "weekend_vs_weekday_delta_pct": delta_pct,
            }
        }

        return self._wrap_response(
            trend_type="daily_trend",
            metric=metric,
            granularity="day_of_week",
            smoothing_method=smoothing_method,
            smoothing_window=result["smoothing_window"],
            filters=filters,
            total_records=result["total_records"],
            time_series=result["records"],
            trend_classification=result["trend_classification"],
            peak_trough=result["peak_trough"],
            summary=result["summary"],
            forecast=forecast,
            window_adjusted=result["window_adjusted"],
            original_window=result["original_window"],
            missing_filled=result["missing_filled"],
            extra=extra,
        )

    def _date_trend(self, params: Dict) -> str:
        """
        Calendar date-level temporal progression analysis.

        Args:
            params: Parameters dict with metric, smoothing, filters, etc.

        Returns:
            JSON string with date trend results.
        """
        metric = params.get("metric", "volume")
        smoothing_window = min(params.get("smoothing_window", 7), 7)
        smoothing_method = params.get("smoothing_method", "sma")
        filters = params.get("filters", [])
        include_forecast = params.get("include_forecast", False)
        min_dp = params.get("min_data_points", 3)
        tw_start = params.get("trend_window_start")
        tw_end = params.get("trend_window_end")

        df = self._apply_filters(self.df.copy(), filters)

        result = self._build_single_metric_trend(
            df, metric, "date", smoothing_window, smoothing_method,
            tw_start, tw_end, min_dp,
        )

        # Add day_of_week_label and is_weekend to each record
        for rec in result["records"]:
            try:
                d = pd.Timestamp(rec["time_point"])
                rec["day_of_week_label"] = DAY_NAMES.get(d.dayofweek, "Unknown")
                rec["is_weekend"] = d.dayofweek in (5, 6)
            except Exception:
                rec["day_of_week_label"] = "Unknown"
                rec["is_weekend"] = False

        dates = result["time_labels"]
        date_range_label = f"{dates[0]} – {dates[-1]}" if dates else "N/A"
        total_days = len(dates)

        forecast = None
        if include_forecast:
            forecast = self._compute_forecast(result["sma_series"], result["time_points"])

        extra = {
            "date_extras": {
                "date_range_label": date_range_label,
                "total_days_analyzed": total_days,
            }
        }

        return self._wrap_response(
            trend_type="date_trend",
            metric=metric,
            granularity="date",
            smoothing_method=smoothing_method,
            smoothing_window=result["smoothing_window"],
            filters=filters,
            total_records=result["total_records"],
            time_series=result["records"],
            trend_classification=result["trend_classification"],
            peak_trough=result["peak_trough"],
            summary=result["summary"],
            forecast=forecast,
            window_adjusted=result["window_adjusted"],
            original_window=result["original_window"],
            missing_filled=result["missing_filled"],
            extra=extra,
        )

    # ------------------------------------------------------------------
    # multi_metric_trend
    # ------------------------------------------------------------------

    def _multi_metric_trend(self, params: Dict) -> str:
        """
        Multiple metrics tracked simultaneously on the same time axis.

        Args:
            params: Parameters dict with metric, secondary_metrics, etc.

        Returns:
            JSON string with multi-metric trend results.
        """
        primary_metric = params.get("metric", "volume")
        secondary = params.get("secondary_metrics", [])
        all_metrics = [primary_metric] + [m for m in secondary if m != primary_metric]
        granularity = params.get("time_granularity", "hour")
        smoothing_window = params.get("smoothing_window", 3)
        smoothing_method = params.get("smoothing_method", "sma")
        filters = params.get("filters", [])
        min_dp = params.get("min_data_points", 3)
        tw_start = params.get("trend_window_start")
        tw_end = params.get("trend_window_end")

        if granularity == "hour":
            smoothing_window = min(smoothing_window, 6)
        elif granularity == "day_of_week":
            smoothing_window = min(smoothing_window, 3)
        else:
            smoothing_window = min(smoothing_window, 7)

        df = self._apply_filters(self.df.copy(), filters)

        per_metric: Dict[str, Dict] = {}
        for m in all_metrics:
            per_metric[m] = self._build_single_metric_trend(
                df, m, granularity, smoothing_window, smoothing_method,
                tw_start, tw_end, min_dp,
            )

        # Normalize each metric to 0–100 for comparison
        normalized: Dict[str, List[float]] = {}
        for m, data in per_metric.items():
            arr = data["raw_arr"]
            mn, mx = float(np.nanmin(arr)), float(np.nanmax(arr))
            if mx == mn:
                normalized[m] = [50.0] * len(arr)
            else:
                normalized[m] = [_safe_round(((v - mn) / (mx - mn)) * 100) for v in arr]

        # Pearson correlation between each pair
        correlations: List[Dict[str, Any]] = []
        keys = list(per_metric.keys())
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                a = per_metric[keys[i]]["raw_arr"]
                b = per_metric[keys[j]]["raw_arr"]
                min_len = min(len(a), len(b))
                if min_len < 3:
                    r_val = None
                else:
                    valid = ~(np.isnan(a[:min_len]) | np.isnan(b[:min_len]))
                    if valid.sum() < 3:
                        r_val = None
                    else:
                        r_val = _safe_round(float(np.corrcoef(a[:min_len][valid], b[:min_len][valid])[0, 1]))
                correlations.append({
                    "metric_a": keys[i],
                    "metric_b": keys[j],
                    "pearson_r": r_val,
                })

        # Find leading metric (simplistic: which has earliest significant move via first derivative)
        leading_metric = primary_metric
        earliest_move = float("inf")
        for m, data in per_metric.items():
            fd = data["sma_series"].diff().abs()
            significant = fd[fd > fd.mean()]
            if len(significant) > 0:
                first_sig_idx = significant.index[0]
                pos = list(data["sma_series"].index).index(first_sig_idx)
                if pos < earliest_move:
                    earliest_move = pos
                    leading_metric = m

        # Build combined time series — merge per-metric records
        first_key = keys[0]
        n_points = len(per_metric[first_key]["records"])
        combined_series: List[Dict[str, Any]] = []
        for idx in range(n_points):
            rec = {
                "time_point": per_metric[first_key]["records"][idx]["time_point"],
                "time_label": per_metric[first_key]["records"][idx]["time_label"],
            }
            for m in keys:
                prefix = m
                m_rec = per_metric[m]["records"][idx] if idx < len(per_metric[m]["records"]) else {}
                rec[f"{prefix}_raw"] = m_rec.get("raw_value")
                rec[f"{prefix}_sma"] = m_rec.get("sma_value")
                rec[f"{prefix}_normalized"] = normalized[m][idx] if idx < len(normalized[m]) else None
            combined_series.append(rec)

        # Use primary metric for classification
        primary_data = per_metric[primary_metric]

        per_metric_classifications = {
            m: data["trend_classification"] for m, data in per_metric.items()
        }

        extra = {
            "per_metric_classifications": per_metric_classifications,
            "metric_correlations": correlations,
            "leading_metric": leading_metric,
            "normalized_scale": "0-100 min-max per metric",
        }

        return self._wrap_response(
            trend_type="multi_metric_trend",
            metric=primary_metric,
            granularity=granularity,
            smoothing_method=smoothing_method,
            smoothing_window=primary_data["smoothing_window"],
            filters=filters,
            total_records=primary_data["total_records"],
            time_series=combined_series,
            trend_classification=primary_data["trend_classification"],
            peak_trough=primary_data["peak_trough"],
            summary=primary_data["summary"],
            window_adjusted=primary_data["window_adjusted"],
            original_window=primary_data["original_window"],
            missing_filled=primary_data["missing_filled"],
            extra=extra,
        )

    # ------------------------------------------------------------------
    # segmented_trend
    # ------------------------------------------------------------------

    def _segmented_trend(self, params: Dict) -> str:
        """
        Same metric computed separately for two or more segments for overlay.

        Args:
            params: Parameters dict with segment_column, segment_values, etc.

        Returns:
            JSON string with segmented trend results.
        """
        metric = params.get("metric", "volume")
        segment_column = data_loader.resolve_column(params.get("segment_column", "")) if params.get("segment_column") else None
        segment_values = params.get("segment_values")
        granularity = params.get("time_granularity", "hour")
        smoothing_window = params.get("smoothing_window", 3)
        smoothing_method = params.get("smoothing_method", "sma")
        filters = params.get("filters", [])
        min_dp = params.get("min_data_points", 3)
        tw_start = params.get("trend_window_start")
        tw_end = params.get("trend_window_end")

        if not segment_column:
            return self._error_response(
                "segmented_trend",
                "segment_column is required for segmented_trend.",
                "Provide segment_column (e.g. 'device_type', 'network_type').",
            )

        if granularity == "hour":
            smoothing_window = min(smoothing_window, 6)
        elif granularity == "day_of_week":
            smoothing_window = min(smoothing_window, 3)
        else:
            smoothing_window = min(smoothing_window, 7)

        df = self._apply_filters(self.df.copy(), filters)

        if segment_column not in df.columns:
            return self._error_response(
                "segmented_trend",
                f"Column '{segment_column}' not found in dataset.",
                "Valid columns include device_type, network_type, transaction_type, sender_bank, etc.",
            )

        if not segment_values:
            segment_values = df[segment_column].dropna().unique().tolist()

        per_segment: Dict[str, Dict] = {}
        for seg in segment_values:
            seg_df = df[df[segment_column] == seg]
            if len(seg_df) == 0:
                continue
            try:
                per_segment[seg] = self._build_single_metric_trend(
                    seg_df, metric, granularity, smoothing_window, smoothing_method,
                    tw_start, tw_end, min_dp,
                )
            except ValueError:
                continue

        if not per_segment:
            return self._error_response(
                "segmented_trend",
                "No segments had enough data for trend analysis.",
                "Try broader filters or a different segment_column.",
            )

        # Build combined time series
        ref_seg = list(per_segment.keys())[0]
        n_points = len(per_segment[ref_seg]["records"])
        combined: List[Dict[str, Any]] = []
        for idx in range(n_points):
            rec = {
                "time_point": per_segment[ref_seg]["records"][idx]["time_point"],
                "time_label": per_segment[ref_seg]["records"][idx]["time_label"],
            }
            for seg, data in per_segment.items():
                if idx < len(data["records"]):
                    rec[f"{seg}_raw"] = data["records"][idx]["raw_value"]
                    rec[f"{seg}_sma"] = data["records"][idx]["sma_value"]
            combined.append(rec)

        # Crossover points
        seg_keys = list(per_segment.keys())
        crossover_points: List[Dict[str, Any]] = []
        if len(seg_keys) >= 2:
            sma_a = per_segment[seg_keys[0]]["sma_arr"]
            sma_b = per_segment[seg_keys[1]]["sma_arr"]
            min_len = min(len(sma_a), len(sma_b))
            for i in range(1, min_len):
                diff_prev = sma_a[i - 1] - sma_b[i - 1]
                diff_curr = sma_a[i] - sma_b[i]
                if diff_prev * diff_curr < 0:  # sign change = crossover
                    crossover_points.append({
                        "time_point": per_segment[ref_seg]["time_labels"][i],
                        "crossing_segments": [seg_keys[0], seg_keys[1]],
                        "description": f"{seg_keys[0]} crosses {'above' if diff_curr > 0 else 'below'} {seg_keys[1]}",
                    })

        # Segment gap series
        segment_gap: List[Dict[str, Any]] = []
        for idx in range(n_points):
            vals = []
            for seg, data in per_segment.items():
                if idx < len(data["sma_arr"]):
                    vals.append(float(data["sma_arr"][idx]))
            if vals:
                segment_gap.append({
                    "time_point": per_segment[ref_seg]["time_labels"][idx] if idx < len(per_segment[ref_seg]["time_labels"]) else idx,
                    "max_segment_value": _safe_round(max(vals)),
                    "min_segment_value": _safe_round(min(vals)),
                    "gap": _safe_round(max(vals) - min(vals)),
                })

        # Convergence / divergence
        if len(segment_gap) >= 3:
            early_gap = np.mean([g["gap"] for g in segment_gap[:len(segment_gap) // 3] if g["gap"] is not None])
            late_gap = np.mean([g["gap"] for g in segment_gap[-len(segment_gap) // 3:] if g["gap"] is not None])
            if late_gap < early_gap * 0.85:
                conv_label = "Converging"
            elif late_gap > early_gap * 1.15:
                conv_label = "Diverging"
            else:
                conv_label = "Stable Gap"
        else:
            conv_label = "Insufficient Data"

        per_segment_classifications = {
            seg: data["trend_classification"] for seg, data in per_segment.items()
        }

        # Use first segment for primary classification
        ref_data = per_segment[ref_seg]

        extra = {
            "per_segment_classifications": per_segment_classifications,
            "crossover_points": crossover_points,
            "segment_gap_series": segment_gap,
            "convergence_divergence_label": conv_label,
        }

        return self._wrap_response(
            trend_type="segmented_trend",
            metric=metric,
            granularity=granularity,
            smoothing_method=smoothing_method,
            smoothing_window=ref_data["smoothing_window"],
            filters=filters,
            total_records=ref_data["total_records"],
            time_series=combined,
            trend_classification=ref_data["trend_classification"],
            peak_trough=ref_data["peak_trough"],
            summary=ref_data["summary"],
            window_adjusted=ref_data["window_adjusted"],
            original_window=ref_data["original_window"],
            missing_filled=ref_data["missing_filled"],
            extra=extra,
        )

    # ------------------------------------------------------------------
    # rolling_anomaly_trend
    # ------------------------------------------------------------------

    def _rolling_anomaly_trend(self, params: Dict) -> str:
        """
        Standard trend plus anomaly detection bands (±2σ, ±3σ).

        Args:
            params: Parameters dict with metric, smoothing, filters, etc.

        Returns:
            JSON string with rolling anomaly trend results.
        """
        metric = params.get("metric", "volume")
        granularity = params.get("time_granularity", "hour")
        smoothing_window = params.get("smoothing_window", 3)
        smoothing_method = params.get("smoothing_method", "sma")
        filters = params.get("filters", [])
        min_dp = params.get("min_data_points", 3)
        tw_start = params.get("trend_window_start")
        tw_end = params.get("trend_window_end")

        if granularity == "hour":
            smoothing_window = min(smoothing_window, 6)
        elif granularity == "day_of_week":
            smoothing_window = min(smoothing_window, 3)
        else:
            smoothing_window = min(smoothing_window, 7)

        df = self._apply_filters(self.df.copy(), filters)

        result = self._build_single_metric_trend(
            df, metric, granularity, smoothing_window, smoothing_method,
            tw_start, tw_end, min_dp,
        )

        raw_series = result["raw_series"]
        sma_series = result["sma_series"]

        # Rolling std
        rolling_std = raw_series.rolling(window=result["smoothing_window"], min_periods=1).std().fillna(0)
        upper_band = sma_series + 2 * rolling_std
        lower_band = sma_series - 2 * rolling_std
        upper_3 = sma_series + 3 * rolling_std
        lower_3 = sma_series - 3 * rolling_std

        anomaly_time_points: List[Dict[str, Any]] = []
        records = result["records"]
        for i, rec in enumerate(records):
            rv = rec["raw_value"]
            if rv is None:
                rec["upper_band"] = _safe_round(float(upper_band.iloc[i]))
                rec["lower_band"] = _safe_round(float(lower_band.iloc[i]))
                rec["is_anomaly"] = False
                rec["anomaly_severity"] = None
                rec["anomaly_direction"] = None
                continue

            ub = float(upper_band.iloc[i])
            lb = float(lower_band.iloc[i])
            ub3 = float(upper_3.iloc[i])
            lb3 = float(lower_3.iloc[i])
            rec["upper_band"] = _safe_round(ub)
            rec["lower_band"] = _safe_round(lb)

            is_anomaly = rv > ub or rv < lb
            rec["is_anomaly"] = is_anomaly
            if is_anomaly:
                if rv > ub3 or rv < lb3:
                    severity = "Severe"
                else:
                    severity = "Mild"
                direction = "Spike" if rv > ub else "Dip"
                rec["anomaly_severity"] = severity
                rec["anomaly_direction"] = direction
                anomaly_time_points.append({
                    "time_point": rec["time_label"],
                    "raw_value": rec["raw_value"],
                    "sma_value": rec["sma_value"],
                    "severity": severity,
                    "direction": direction,
                })
            else:
                rec["anomaly_severity"] = None
                rec["anomaly_direction"] = None

        extra = {
            "anomaly_time_points": anomaly_time_points,
            "total_anomalies_detected": len(anomaly_time_points),
        }

        return self._wrap_response(
            trend_type="rolling_anomaly_trend",
            metric=metric,
            granularity=granularity,
            smoothing_method=smoothing_method,
            smoothing_window=result["smoothing_window"],
            filters=filters,
            total_records=result["total_records"],
            time_series=records,
            trend_classification=result["trend_classification"],
            peak_trough=result["peak_trough"],
            summary=result["summary"],
            window_adjusted=result["window_adjusted"],
            original_window=result["original_window"],
            missing_filled=result["missing_filled"],
            extra=extra,
        )

    # ------------------------------------------------------------------
    # acceleration_trend
    # ------------------------------------------------------------------

    def _acceleration_trend(self, params: Dict) -> str:
        """
        Rate of change (velocity) and acceleration analysis.

        Args:
            params: Parameters dict with metric, smoothing, filters, etc.

        Returns:
            JSON string with acceleration trend results.
        """
        metric = params.get("metric", "volume")
        granularity = params.get("time_granularity", "hour")
        smoothing_window = params.get("smoothing_window", 3)
        smoothing_method = params.get("smoothing_method", "sma")
        filters = params.get("filters", [])
        min_dp = params.get("min_data_points", 3)
        tw_start = params.get("trend_window_start")
        tw_end = params.get("trend_window_end")

        if granularity == "hour":
            smoothing_window = min(smoothing_window, 6)
        elif granularity == "day_of_week":
            smoothing_window = min(smoothing_window, 3)
        else:
            smoothing_window = min(smoothing_window, 7)

        df = self._apply_filters(self.df.copy(), filters)

        result = self._build_single_metric_trend(
            df, metric, granularity, smoothing_window, smoothing_method,
            tw_start, tw_end, min_dp,
        )

        sma_series = result["sma_series"]
        first_deriv = self._compute_first_derivative(sma_series)
        second_deriv = self._compute_second_derivative(first_deriv)

        # Smooth the first derivative
        smoothed_velocity, _, _ = self._apply_smoothing(first_deriv.fillna(0), result["smoothing_window"], smoothing_method)

        records = result["records"]
        inflection_points: List[Dict[str, Any]] = []
        max_accel_val = 0.0
        max_accel_point = None

        for i, rec in enumerate(records):
            fd_val = float(first_deriv.iloc[i]) if not np.isnan(first_deriv.iloc[i]) else None
            sd_val = float(second_deriv.iloc[i]) if i < len(second_deriv) and not np.isnan(second_deriv.iloc[i]) else None
            sv_val = float(smoothed_velocity.iloc[i]) if not np.isnan(smoothed_velocity.iloc[i]) else None

            rec["first_derivative"] = _safe_round(fd_val)
            rec["second_derivative"] = _safe_round(sd_val)
            rec["smoothed_velocity"] = _safe_round(sv_val)

            # Velocity label
            if fd_val is not None:
                if fd_val > 0.001:
                    rec["velocity_label"] = "Increasing"
                elif fd_val < -0.001:
                    rec["velocity_label"] = "Decreasing"
                else:
                    rec["velocity_label"] = "Stable"
            else:
                rec["velocity_label"] = None

            # Acceleration label
            if sd_val is not None:
                if sd_val > 0.001:
                    rec["acceleration_label"] = "Accelerating"
                elif sd_val < -0.001:
                    rec["acceleration_label"] = "Decelerating"
                else:
                    rec["acceleration_label"] = "Steady"
            else:
                rec["acceleration_label"] = None

            # Track max acceleration
            if sd_val is not None and abs(sd_val) > abs(max_accel_val):
                max_accel_val = sd_val
                max_accel_point = rec["time_label"]

            # Inflection points (first derivative sign change)
            if i > 0 and fd_val is not None:
                prev_fd = float(first_deriv.iloc[i - 1]) if not np.isnan(first_deriv.iloc[i - 1]) else None
                if prev_fd is not None and fd_val * prev_fd < 0:
                    inflection_points.append({
                        "time_point": rec["time_label"],
                        "from_direction": "Increasing" if prev_fd > 0 else "Decreasing",
                        "to_direction": "Increasing" if fd_val > 0 else "Decreasing",
                    })

        extra = {
            "maximum_acceleration_point": max_accel_point,
            "maximum_acceleration_value": _safe_round(max_accel_val),
            "inflection_points": inflection_points,
            "total_inflection_points": len(inflection_points),
        }

        return self._wrap_response(
            trend_type="acceleration_trend",
            metric=metric,
            granularity=granularity,
            smoothing_method=smoothing_method,
            smoothing_window=result["smoothing_window"],
            filters=filters,
            total_records=result["total_records"],
            time_series=records,
            trend_classification=result["trend_classification"],
            peak_trough=result["peak_trough"],
            summary=result["summary"],
            window_adjusted=result["window_adjusted"],
            original_window=result["original_window"],
            missing_filled=result["missing_filled"],
            extra=extra,
        )

    # ------------------------------------------------------------------
    # comparative_period_trend
    # ------------------------------------------------------------------

    def _comparative_period_trend(self, params: Dict) -> str:
        """
        Compare trend patterns between two time periods.

        Args:
            params: Parameters dict with period_a_filter, period_b_filter, etc.

        Returns:
            JSON string with comparative period trend results.
        """
        metric = params.get("metric", "volume")
        granularity = params.get("time_granularity", "hour")
        smoothing_window = params.get("smoothing_window", 3)
        smoothing_method = params.get("smoothing_method", "sma")
        filters = params.get("filters", [])
        period_a_filter = params.get("period_a_filter", [])
        period_b_filter = params.get("period_b_filter", [])
        period_a_label = params.get("period_a_label", "Period A")
        period_b_label = params.get("period_b_label", "Period B")
        min_dp = params.get("min_data_points", 3)
        tw_start = params.get("trend_window_start")
        tw_end = params.get("trend_window_end")

        if granularity == "hour":
            smoothing_window = min(smoothing_window, 6)
        elif granularity == "day_of_week":
            smoothing_window = min(smoothing_window, 3)
        else:
            smoothing_window = min(smoothing_window, 7)

        base_df = self._apply_filters(self.df.copy(), filters)

        df_a = self._apply_filters(base_df.copy(), period_a_filter)
        df_b = self._apply_filters(base_df.copy(), period_b_filter)

        try:
            result_a = self._build_single_metric_trend(
                df_a, metric, granularity, smoothing_window, smoothing_method,
                tw_start, tw_end, min_dp,
            )
        except ValueError as e:
            return self._error_response("comparative_period_trend", f"Period A: {e}", "Broaden period A filter.")

        try:
            result_b = self._build_single_metric_trend(
                df_b, metric, granularity, smoothing_window, smoothing_method,
                tw_start, tw_end, min_dp,
            )
        except ValueError as e:
            return self._error_response("comparative_period_trend", f"Period B: {e}", "Broaden period B filter.")

        # Build combined series
        n_a = len(result_a["records"])
        n_b = len(result_b["records"])
        n_points = min(n_a, n_b)
        combined: List[Dict[str, Any]] = []
        delta_series: List[Dict[str, Any]] = []
        for i in range(n_points):
            rec_a = result_a["records"][i]
            rec_b = result_b["records"][i]
            a_val = rec_a["raw_value"]
            b_val = rec_b["raw_value"]
            delta = _safe_round(a_val - b_val) if (a_val is not None and b_val is not None) else None

            combined.append({
                "time_point": rec_a["time_point"],
                "time_label": rec_a["time_label"],
                f"{period_a_label}_raw": rec_a["raw_value"],
                f"{period_a_label}_sma": rec_a["sma_value"],
                f"{period_b_label}_raw": rec_b["raw_value"],
                f"{period_b_label}_sma": rec_b["sma_value"],
                "delta_raw": delta,
            })
            delta_series.append({"time_point": rec_a["time_label"], "delta": delta})

        # Delta trend classification
        delta_vals = [d["delta"] for d in delta_series if d["delta"] is not None]
        if len(delta_vals) >= 3:
            delta_pd = pd.Series(delta_vals)
            delta_sma, _, _ = self._apply_smoothing(delta_pd, max(2, min(3, len(delta_vals))), "sma")
            delta_direction = self._classify_trend_direction(delta_sma)
        else:
            delta_direction = {"direction": "Insufficient Data", "pct_change_early_to_late": 0.0, "early_period_avg": 0.0, "late_period_avg": 0.0}

        # Correlation between the two period SMA series
        sma_a = result_a["sma_arr"][:n_points]
        sma_b = result_b["sma_arr"][:n_points]
        if n_points >= 3:
            pearson_r = _safe_round(float(np.corrcoef(sma_a, sma_b)[0, 1]))
        else:
            pearson_r = None
        periods_match = bool(pearson_r is not None and pearson_r > 0.8)

        extra = {
            "period_a_classification": result_a["trend_classification"],
            "period_b_classification": result_b["trend_classification"],
            "period_a_label": period_a_label,
            "period_b_label": period_b_label,
            "period_delta_series": delta_series,
            "delta_trend_classification": delta_direction,
            "pearson_r_between_periods": pearson_r,
            "periods_match_closely": periods_match,
        }

        return self._wrap_response(
            trend_type="comparative_period_trend",
            metric=metric,
            granularity=granularity,
            smoothing_method=smoothing_method,
            smoothing_window=result_a["smoothing_window"],
            filters=filters,
            total_records=len(base_df),
            time_series=combined,
            trend_classification=result_a["trend_classification"],
            peak_trough=result_a["peak_trough"],
            summary=result_a["summary"],
            window_adjusted=result_a["window_adjusted"],
            original_window=result_a["original_window"],
            missing_filled=result_a["missing_filled"],
            extra=extra,
        )

    # ------------------------------------------------------------------
    # cumulative_trend
    # ------------------------------------------------------------------

    def _cumulative_trend(self, params: Dict) -> str:
        """
        Running cumulative total of a metric over time.

        Args:
            params: Parameters dict with metric, smoothing, filters, etc.

        Returns:
            JSON string with cumulative trend results.
        """
        metric = params.get("metric", "volume")
        granularity = params.get("time_granularity", "hour")
        smoothing_window = params.get("smoothing_window", 3)
        smoothing_method = params.get("smoothing_method", "sma")
        filters = params.get("filters", [])
        min_dp = params.get("min_data_points", 3)
        tw_start = params.get("trend_window_start")
        tw_end = params.get("trend_window_end")

        if granularity == "hour":
            smoothing_window = min(smoothing_window, 6)
        elif granularity == "day_of_week":
            smoothing_window = min(smoothing_window, 3)
        else:
            smoothing_window = min(smoothing_window, 7)

        df = self._apply_filters(self.df.copy(), filters)

        result = self._build_single_metric_trend(
            df, metric, granularity, smoothing_window, smoothing_method,
            tw_start, tw_end, min_dp,
        )

        records = result["records"]
        raw_vals = [r["raw_value"] if r["raw_value"] is not None else 0 for r in records]
        cumulative = np.cumsum(raw_vals)
        total = cumulative[-1] if len(cumulative) > 0 else 0

        halfway_point = None
        steepest_start = None
        steepest_end = None
        steepest_growth = 0.0

        for i, rec in enumerate(records):
            rec["cumulative_raw"] = _safe_round(float(cumulative[i]))
            rec["cumulative_pct"] = _safe_round((float(cumulative[i]) / total) * 100) if total != 0 else 0.0

            # Halfway point
            if halfway_point is None and total > 0 and cumulative[i] >= total / 2:
                halfway_point = rec["time_label"]

        # Steepest growth window (consecutive 3-point window with max cumulative jump)
        if len(raw_vals) >= 3:
            for i in range(len(raw_vals) - 2):
                window_sum = sum(raw_vals[i:i + 3])
                if window_sum > steepest_growth:
                    steepest_growth = window_sum
                    steepest_start = records[i]["time_label"]
                    steepest_end = records[min(i + 2, len(records) - 1)]["time_label"]

        extra = {
            "cumulative_extras": {
                "halfway_point": halfway_point,
                "steepest_growth_period": f"{steepest_start} to {steepest_end}" if steepest_start else None,
                "steepest_growth_value": _safe_round(steepest_growth),
                "final_cumulative_total": _safe_round(float(total)),
            }
        }

        return self._wrap_response(
            trend_type="cumulative_trend",
            metric=metric,
            granularity=granularity,
            smoothing_method=smoothing_method,
            smoothing_window=result["smoothing_window"],
            filters=filters,
            total_records=result["total_records"],
            time_series=records,
            trend_classification=result["trend_classification"],
            peak_trough=result["peak_trough"],
            summary=result["summary"],
            window_adjusted=result["window_adjusted"],
            original_window=result["original_window"],
            missing_filled=result["missing_filled"],
            extra=extra,
        )

    # ------------------------------------------------------------------
    # volatility_trend
    # ------------------------------------------------------------------

    def _volatility_trend(self, params: Dict) -> str:
        """
        Rolling standard deviation over time — measures stability vs instability.

        Args:
            params: Parameters dict with metric, smoothing, filters, etc.

        Returns:
            JSON string with volatility trend results.
        """
        metric = params.get("metric", "volume")
        granularity = params.get("time_granularity", "hour")
        smoothing_window = params.get("smoothing_window", 3)
        smoothing_method = params.get("smoothing_method", "sma")
        filters = params.get("filters", [])
        min_dp = params.get("min_data_points", 3)
        tw_start = params.get("trend_window_start")
        tw_end = params.get("trend_window_end")

        if granularity == "hour":
            smoothing_window = min(smoothing_window, 6)
        elif granularity == "day_of_week":
            smoothing_window = min(smoothing_window, 3)
        else:
            smoothing_window = min(smoothing_window, 7)

        df = self._apply_filters(self.df.copy(), filters)

        result = self._build_single_metric_trend(
            df, metric, granularity, smoothing_window, smoothing_method,
            tw_start, tw_end, min_dp,
        )

        raw_series = result["raw_series"]
        sma_series = result["sma_series"]
        window = result["smoothing_window"]

        rolling_std = raw_series.rolling(window=window, min_periods=1).std().fillna(0)
        rolling_mean = raw_series.rolling(window=window, min_periods=1).mean()
        rolling_cv = (rolling_std / rolling_mean.replace(0, np.nan) * 100).fillna(0)

        records = result["records"]
        most_stable_idx = None
        most_volatile_idx = None
        min_cv = float("inf")
        max_cv = 0.0

        for i, rec in enumerate(records):
            std_val = float(rolling_std.iloc[i])
            cv_val = float(rolling_cv.iloc[i])

            rec["rolling_std"] = _safe_round(std_val)
            rec["rolling_cv_pct"] = _safe_round(cv_val)

            if cv_val < 10:
                rec["stability_classification"] = "Stable"
            elif cv_val < 25:
                rec["stability_classification"] = "Moderate"
            else:
                rec["stability_classification"] = "Volatile"

            if cv_val < min_cv:
                min_cv = cv_val
                most_stable_idx = i
            if cv_val > max_cv:
                max_cv = cv_val
                most_volatile_idx = i

        most_stable_period = records[most_stable_idx]["time_label"] if most_stable_idx is not None else None
        most_volatile_period = records[most_volatile_idx]["time_label"] if most_volatile_idx is not None else None

        extra = {
            "volatility_extras": {
                "most_stable_period": most_stable_period,
                "most_stable_cv_pct": _safe_round(min_cv),
                "most_volatile_period": most_volatile_period,
                "most_volatile_cv_pct": _safe_round(max_cv),
            }
        }

        return self._wrap_response(
            trend_type="volatility_trend",
            metric=metric,
            granularity=granularity,
            smoothing_method=smoothing_method,
            smoothing_window=result["smoothing_window"],
            filters=filters,
            total_records=result["total_records"],
            time_series=records,
            trend_classification=result["trend_classification"],
            peak_trough=result["peak_trough"],
            summary=result["summary"],
            window_adjusted=result["window_adjusted"],
            original_window=result["original_window"],
            missing_filled=result["missing_filled"],
            extra=extra,
        )


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------

def create_trend_tool() -> StructuredTool:
    """
    Factory function to create the trend analysis tool for LangChain.

    Returns:
        StructuredTool configured for time-series trend analysis.
    """
    tool_instance = TrendTool()

    return StructuredTool.from_function(
        func=tool_instance.analyze,
        name="trend_tool",
        description=(
            "For ALL time-series and trend questions. Use this when questions involve "
            "how a metric changes over time, whether something is increasing or decreasing, "
            "trend direction, patterns across hours or days, trajectory analysis, or SMA "
            "smoothing. Use this for questions containing words like 'trend,' 'over time,' "
            "'increasing,' 'decreasing,' 'pattern,' 'trajectory,' 'moving average,' "
            "'how does X change,' 'getting better/worse,' 'rising/falling,' and "
            "'across the day/week.' Input: trend_type (string: hourly_trend, daily_trend, "
            "date_trend, multi_metric_trend, segmented_trend, rolling_anomaly_trend, "
            "acceleration_trend, comparative_period_trend, cumulative_trend, volatility_trend) "
            "and parameters (JSON string with metric, time_granularity, smoothing_window, "
            "smoothing_method, filters, segment_column, segment_values, secondary_metrics, "
            "include_forecast, period_a_filter, period_b_filter, period_a_label, period_b_label)."
        ),
        args_schema=TrendInput,
    )
