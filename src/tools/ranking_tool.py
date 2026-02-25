"""
Ranking Tool for PayInsight AI

This module provides comprehensive ranking, leaderboard, top-N, bottom-N,
share-of-wallet, and distribution analysis capabilities for transaction data.
It is the single authoritative handler for all "which is most/least",
"top N", "rank by", and "share of total" questions in the system.

Every ranking output includes share-of-wallet (volume share, value share,
wallet concentration ratio), cumulative shares, performance tiers, and
Pareto insights — delivering a complete ranking intelligence report.

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

class RankingInput(BaseModel):
    """Input schema for ranking tool."""

    ranking_type: str = Field(
        description=(
            "Type of ranking: top_n, bottom_n, full_ranking, share_of_wallet, "
            "fraud_ranking, failure_ranking, multi_metric_ranking, pareto_analysis, "
            "state_ranking, category_ranking"
        )
    )
    parameters: str = Field(
        description=(
            "JSON string with ranking parameters: dimension (column to rank), "
            "metric (volume, total_amount, avg_amount, failure_rate, fraud_rate, "
            "success_rate, fraud_by_value_rate, pending_rate), top_n (int), "
            "filters (list), ascending (bool), secondary_metrics (list), "
            "include_pareto (bool), tier_count (int), tier_labels (list), "
            "composite_weights (dict for multi_metric_ranking)"
        )
    )


# ---------------------------------------------------------------------------
# State-to-region mapping
# ---------------------------------------------------------------------------

_STATE_REGION_MAP: Dict[str, str] = {
    # North
    "Delhi": "North", "Uttar Pradesh": "North", "UP": "North",
    "Haryana": "North", "Punjab": "North", "Rajasthan": "North",
    "Himachal Pradesh": "North", "HP": "North",
    "Jammu and Kashmir": "North", "J&K": "North",
    "Uttarakhand": "North", "Chandigarh": "North",
    # South
    "Tamil Nadu": "South", "Karnataka": "South", "Kerala": "South",
    "Andhra Pradesh": "South", "Telangana": "South", "Puducherry": "South",
    # West
    "Maharashtra": "West", "Gujarat": "West", "Goa": "West",
    # East
    "West Bengal": "East", "Bihar": "East", "Odisha": "East",
    "Jharkhand": "East", "Assam": "East",
    "Meghalaya": "East", "Tripura": "East", "Manipur": "East",
    "Mizoram": "East", "Nagaland": "East", "Arunachal Pradesh": "East",
    "Sikkim": "East",
    # Central
    "Madhya Pradesh": "Central", "MP": "Central",
    "Chhattisgarh": "Central",
}

_ESSENTIAL_CATEGORIES = frozenset({
    "Grocery", "Healthcare", "Utilities", "Education", "Transport", "Fuel",
})
_DISCRETIONARY_CATEGORIES = frozenset({
    "Food", "Entertainment", "Shopping",
})


# ---------------------------------------------------------------------------
# Main tool class
# ---------------------------------------------------------------------------

class RankingTool:
    """
    Comprehensive ranking and leaderboard tool for transaction data.

    Handles top-N, bottom-N, full-ranking, share-of-wallet, fraud-ranking,
    failure-ranking, multi-metric composite ranking, Pareto (80-20) analysis,
    state-level geographic ranking, and merchant-category ranking — each
    enriched with share-of-wallet layers, cumulative shares, performance
    tiers, and Pareto insights.
    """

    def __init__(self) -> None:
        """Initialize RankingTool with data from the singleton loader."""
        self.df: pd.DataFrame = data_loader.load_data()
        self.total_records: int = len(self.df)

    # ==================================================================
    # Public entry point
    # ==================================================================

    def rank(self, ranking_type: str, parameters: str) -> str:
        """
        Main entry point for ranking operations.

        Args:
            ranking_type: The kind of ranking to produce (e.g. top_n, fraud_ranking).
            parameters: JSON string with dimension, metric, filters, and config.

        Returns:
            JSON string with the ranking results in the standardised output format.
        """
        try:
            params: Dict[str, Any] = json.loads(parameters) if parameters else {}
        except json.JSONDecodeError as exc:
            return self._error_response(
                ranking_type,
                f"Invalid JSON in parameters: {exc}",
                "Ensure parameters is a valid JSON string.",
            )

        dispatch: Dict[str, Any] = {
            "top_n": self._rank_top_n,
            "bottom_n": self._rank_bottom_n,
            "full_ranking": self._rank_full,
            "share_of_wallet": self._rank_share_of_wallet,
            "fraud_ranking": self._rank_fraud,
            "failure_ranking": self._rank_failure,
            "multi_metric_ranking": self._rank_multi_metric,
            "pareto_analysis": self._rank_pareto,
            "state_ranking": self._rank_state,
            "category_ranking": self._rank_category,
        }

        if ranking_type not in dispatch:
            return self._error_response(
                ranking_type,
                f"Unknown ranking_type: {ranking_type}",
                f"Valid types: {', '.join(dispatch.keys())}",
            )

        try:
            return dispatch[ranking_type](params)
        except Exception as exc:
            return self._error_response(
                ranking_type,
                f"Ranking failed: {exc}",
                "Check your parameters and try again.",
            )

    # ==================================================================
    # Internal helpers — filtering
    # ==================================================================

    def _apply_filters(self, df: pd.DataFrame, filters: List[Dict]) -> pd.DataFrame:
        """
        Apply a list of filter conditions to *df* and return the subset.

        Args:
            df: Source DataFrame.
            filters: List of dicts each with column, operator, value.

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

    # ==================================================================
    # Internal helpers — group metric computation
    # ==================================================================

    def _compute_group_metrics(
        self, df: pd.DataFrame, dimension: str
    ) -> pd.DataFrame:
        """
        Group *df* by *dimension* and compute the full standard metric suite.

        Args:
            df: Filtered DataFrame.
            dimension: Column name to group by.

        Returns:
            DataFrame with one row per unique dimension value and all metrics.
        """
        grand_total_count: int = len(df)
        grand_total_amount: float = float(df["amount_inr"].sum())

        # --- vectorised aggregation ------------------------------------------------
        agg = df.groupby(dimension, dropna=False).agg(
            total_transactions=("transaction_id", "count"),
            total_amount=("amount_inr", "sum"),
            avg_amount=("amount_inr", "mean"),
            median_amount=("amount_inr", "median"),
            success_count=("transaction_status", lambda s: (s == "SUCCESS").sum()),
            failed_count=("transaction_status", lambda s: (s == "FAILED").sum()),
            pending_count=("transaction_status", lambda s: (s == "PENDING").sum()),
            fraud_count=("fraud_flag", "sum"),
            fraud_amount=("amount_inr", lambda a: float(a[df.loc[a.index, "fraud_flag"] == True].sum())),  # noqa: E712
        ).reset_index()

        # rates
        n = agg["total_transactions"]
        agg["success_rate_pct"] = np.where(n > 0, np.round(agg["success_count"] / n * 100, 2), 0.0)
        agg["failure_rate_pct"] = np.where(n > 0, np.round(agg["failed_count"] / n * 100, 2), 0.0)
        agg["pending_rate_pct"] = np.where(n > 0, np.round(agg["pending_count"] / n * 100, 2), 0.0)
        agg["fraud_rate_pct"] = np.where(n > 0, np.round(agg["fraud_count"] / n * 100, 2), 0.0)
        agg["fraud_by_value_rate_pct"] = np.where(
            agg["total_amount"] > 0,
            np.round(agg["fraud_amount"] / agg["total_amount"] * 100, 2),
            0.0,
        )

        # shares
        agg["share_of_total_volume_pct"] = np.where(
            grand_total_count > 0,
            np.round(agg["total_transactions"] / grand_total_count * 100, 2),
            0.0,
        )
        agg["share_of_total_amount_pct"] = np.where(
            grand_total_amount > 0,
            np.round(agg["total_amount"] / grand_total_amount * 100, 2),
            0.0,
        )

        # wallet concentration ratio
        agg["wallet_concentration_ratio"] = np.where(
            agg["share_of_total_volume_pct"] > 0,
            np.round(agg["share_of_total_amount_pct"] / agg["share_of_total_volume_pct"], 2),
            0.0,
        )

        # round amounts
        agg["total_amount"] = np.round(agg["total_amount"], 2)
        agg["avg_amount"] = np.round(agg["avg_amount"], 2)
        agg["median_amount"] = np.round(agg["median_amount"], 2)

        return agg

    # ==================================================================
    # Internal helpers — ranking fields
    # ==================================================================

    def _get_sort_column(self, metric: str) -> str:
        """
        Map a user-facing metric name to the corresponding DataFrame column.

        Args:
            metric: Metric name from parameters.

        Returns:
            DataFrame column name to sort on.
        """
        mapping: Dict[str, str] = {
            "volume": "total_transactions",
            "total_amount": "total_amount",
            "avg_amount": "avg_amount",
            "failure_rate": "failure_rate_pct",
            "fraud_rate": "fraud_rate_pct",
            "success_rate": "success_rate_pct",
            "fraud_by_value_rate": "fraud_by_value_rate_pct",
            "pending_rate": "pending_rate_pct",
        }
        return mapping.get(metric, "total_transactions")

    def _add_ranking_fields(
        self,
        agg: pd.DataFrame,
        sort_col: str,
        ascending: bool = False,
    ) -> pd.DataFrame:
        """
        Sort *agg*, assign rank, percentile, cumulative shares, vs_average,
        and gap_to_rank_1.

        Args:
            agg: Aggregated DataFrame with metrics.
            sort_col: Column to sort and rank by.
            ascending: Sort direction.

        Returns:
            DataFrame with ranking fields added.
        """
        agg = agg.sort_values(sort_col, ascending=ascending).reset_index(drop=True)
        agg["rank"] = range(1, len(agg) + 1)

        total_items = len(agg)
        if total_items > 1:
            agg["percentile"] = np.round(
                (1 - (agg["rank"] - 1) / (total_items - 1)) * 100, 2
            )
        else:
            agg["percentile"] = 100.0

        # cumulative shares (always computed in descending metric order)
        sort_desc = agg.sort_values(sort_col, ascending=False)
        cum_vol = sort_desc["share_of_total_volume_pct"].cumsum().round(2)
        cum_amt = sort_desc["share_of_total_amount_pct"].cumsum().round(2)
        agg.loc[sort_desc.index, "cumulative_volume_share_pct"] = cum_vol.values
        agg.loc[sort_desc.index, "cumulative_amount_share_pct"] = cum_amt.values
        # re-sort to original rank order
        agg = agg.sort_values("rank").reset_index(drop=True)

        # vs dimension average
        dim_avg = agg[sort_col].mean()
        agg["vs_dimension_average_pct"] = np.where(
            dim_avg != 0,
            np.round((agg[sort_col] - dim_avg) / abs(dim_avg) * 100, 2),
            0.0,
        )

        # gap to rank 1
        top_val = agg.loc[agg["rank"] == 1, sort_col].values[0] if len(agg) > 0 else 0
        agg["gap_to_rank_1_absolute"] = np.round(top_val - agg[sort_col], 2)
        agg["gap_to_rank_1_pct"] = np.where(
            top_val != 0,
            np.round((top_val - agg[sort_col]) / abs(top_val) * 100, 2),
            0.0,
        )

        return agg

    # ==================================================================
    # Internal helpers — share-of-wallet
    # ==================================================================

    def _compute_share_of_wallet(self, row: pd.Series) -> Dict[str, float]:
        """
        Build the share-of-wallet block for a single ranked item.

        Args:
            row: A single row from the aggregated DataFrame.

        Returns:
            Dictionary with volume_share_pct, amount_share_pct,
            wallet_concentration_ratio, and cumulative shares.
        """
        wcr = float(row.get("wallet_concentration_ratio", 0.0))
        return {
            "volume_share_pct": round(float(row.get("share_of_total_volume_pct", 0.0)), 2),
            "amount_share_pct": round(float(row.get("share_of_total_amount_pct", 0.0)), 2),
            "wallet_concentration_ratio": round(wcr, 2),
            "wallet_concentration_label": (
                "High-Value Segment" if wcr > 1.2
                else ("Balanced" if wcr >= 0.8 else "High-Volume Low-Value Segment")
            ),
            "cumulative_volume_share_pct": round(float(row.get("cumulative_volume_share_pct", 0.0)), 2),
            "cumulative_amount_share_pct": round(float(row.get("cumulative_amount_share_pct", 0.0)), 2),
        }

    # ==================================================================
    # Internal helpers — tiers
    # ==================================================================

    def _assign_tiers(
        self,
        agg: pd.DataFrame,
        tier_count: int = 3,
        tier_labels: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Assign performance tiers based on equal percentile bands.

        Args:
            agg: Aggregated DataFrame with 'rank' and 'percentile'.
            tier_count: Number of tiers.
            tier_labels: Optional custom labels per tier.

        Returns:
            DataFrame with 'tier' column added.
        """
        if tier_labels is None:
            tier_labels = ["Top Tier", "Mid Tier", "Low Tier"]
        # Ensure we have the right number of labels
        while len(tier_labels) < tier_count:
            tier_labels.append(f"Tier {len(tier_labels) + 1}")
        tier_labels = tier_labels[:tier_count]

        total = len(agg)
        if total == 0:
            agg["tier"] = pd.Series(dtype=str)
            return agg
        if total == 1:
            agg["tier"] = tier_labels[0]
            return agg

        # Use rank to assign tier: rank 1..ceil(total/tier_count) → top tier, etc.
        band_size = math.ceil(total / tier_count)
        tiers = []
        for r in agg["rank"]:
            idx = min(int((r - 1) // band_size), tier_count - 1)
            tiers.append(tier_labels[idx])
        agg["tier"] = tiers
        return agg

    # ==================================================================
    # Internal helpers — Pareto
    # ==================================================================

    def _compute_pareto_insights(
        self, agg: pd.DataFrame, sort_col: str
    ) -> Dict[str, Any]:
        """
        Compute Pareto / 80-20 insights from the aggregated data.

        Args:
            agg: Aggregated DataFrame sorted by rank.
            sort_col: The primary metric column used for ranking.

        Returns:
            Dictionary with threshold ranks, concentration index, and label.
        """
        if agg.empty:
            return self._empty_pareto()

        # Use metric-based cumulative share for thresholds
        desc = agg.sort_values(sort_col, ascending=False).reset_index(drop=True)
        metric_total = desc[sort_col].sum()
        if metric_total == 0:
            return self._empty_pareto()

        cum_share = (desc[sort_col].cumsum() / metric_total * 100).round(2)

        thresholds = {50: None, 75: None, 80: None, 90: None}
        for pct in thresholds:
            mask = cum_share >= pct
            if mask.any():
                thresholds[pct] = int(mask.idxmax()) + 1  # 1-based rank

        # Concentration index (HHI-style): sum of squared share fractions
        shares = desc[sort_col] / metric_total
        hhi = float((shares ** 2).sum())
        hhi = round(hhi, 4)

        if hhi >= 0.25:
            label = "Highly Concentrated"
        elif hhi >= 0.10:
            label = "Moderately Concentrated"
        else:
            label = "Evenly Distributed"

        return {
            "top_50pct_threshold_rank": thresholds[50],
            "top_75pct_threshold_rank": thresholds[75],
            "top_80pct_threshold_rank": thresholds[80],
            "top_90pct_threshold_rank": thresholds[90],
            "concentration_index": hhi,
            "concentration_label": label,
        }

    def _compute_concentration_index(self, values: pd.Series) -> float:
        """
        Compute HHI-style concentration index from a Series of absolute values.

        Args:
            values: Numeric Series (e.g., transaction counts per group).

        Returns:
            Float between 0 and 1.
        """
        total = values.sum()
        if total == 0:
            return 0.0
        shares = values / total
        return round(float((shares ** 2).sum()), 4)

    def _empty_pareto(self) -> Dict[str, Any]:
        """Return zeroed Pareto block."""
        return {
            "top_50pct_threshold_rank": None,
            "top_75pct_threshold_rank": None,
            "top_80pct_threshold_rank": None,
            "top_90pct_threshold_rank": None,
            "concentration_index": 0.0,
            "concentration_label": "Evenly Distributed",
        }

    # ==================================================================
    # Internal helpers — tier summary
    # ==================================================================

    def _build_tier_summary(
        self, agg: pd.DataFrame, sort_col: str
    ) -> Dict[str, Any]:
        """
        Build a summary dictionary keyed by tier label.

        Args:
            agg: Aggregated DataFrame with 'tier' and metric columns.
            sort_col: The primary metric column.

        Returns:
            Dict mapping tier label → {count, combined_share, avg_metric_value}.
        """
        if "tier" not in agg.columns or agg.empty:
            return {}
        summary: Dict[str, Any] = {}
        metric_total = agg[sort_col].sum()
        for tier_label, group in agg.groupby("tier", sort=False):
            summary[str(tier_label)] = {
                "count": int(len(group)),
                "combined_share_pct": round(
                    float(group[sort_col].sum() / metric_total * 100) if metric_total else 0.0, 2
                ),
                "avg_metric_value": round(float(group[sort_col].mean()), 2),
            }
        return summary

    # ==================================================================
    # Internal helpers — summary generation
    # ==================================================================

    def _generate_summary(
        self,
        agg: pd.DataFrame,
        dimension: str,
        sort_col: str,
        metric: str,
        pareto: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Produce the summary block with key_finding, top/bottom performers,
        wallet concentration highlight, and Pareto statement.

        Args:
            agg: Ranked DataFrame (sorted by rank ascending).
            dimension: Dimension column name.
            sort_col: Column the data is ranked by.
            metric: Human-readable metric name.
            pareto: Pareto insights dict.

        Returns:
            Summary dictionary.
        """
        if agg.empty:
            return {
                "key_finding": "No data available for the requested ranking.",
                "top_performer": "N/A",
                "bottom_performer": "N/A",
                "most_concentrated_value": "N/A",
                "pareto_statement": "N/A",
            }

        top_row = agg.iloc[0]
        bottom_row = agg.iloc[-1]

        top_label = str(top_row[dimension])
        top_value = top_row[sort_col]
        top_vol_share = top_row.get("share_of_total_volume_pct", 0.0)
        top_wcr = top_row.get("wallet_concentration_ratio", 0.0)

        bottom_label = str(bottom_row[dimension])
        bottom_value = bottom_row[sort_col]

        # most concentrated wallet
        if "wallet_concentration_ratio" in agg.columns:
            most_conc_idx = agg["wallet_concentration_ratio"].idxmax()
            most_conc_label = str(agg.loc[most_conc_idx, dimension])
            most_conc_ratio = round(float(agg.loc[most_conc_idx, "wallet_concentration_ratio"]), 2)
        else:
            most_conc_label = top_label
            most_conc_ratio = 0.0

        # format metric value
        if "rate" in sort_col or "pct" in sort_col:
            top_val_str = f"{round(float(top_value), 2)}%"
            bottom_val_str = f"{round(float(bottom_value), 2)}%"
        elif sort_col in ("total_transactions",):
            top_val_str = f"{int(top_value):,} transactions"
            bottom_val_str = f"{int(bottom_value):,} transactions"
        elif sort_col in ("total_amount", "avg_amount", "median_amount"):
            top_val_str = f"₹{round(float(top_value), 2):,.2f}"
            bottom_val_str = f"₹{round(float(bottom_value), 2):,.2f}"
        else:
            top_val_str = str(round(float(top_value), 2))
            bottom_val_str = str(round(float(bottom_value), 2))

        # Pareto statement
        p80_rank = pareto.get("top_80pct_threshold_rank")
        total_unique = len(agg)
        if p80_rank and total_unique:
            pareto_stmt = (
                f"Top {p80_rank} {dimension} values account for ~80% of total {metric}"
                f" ({p80_rank} out of {total_unique})."
            )
        else:
            pareto_stmt = f"All {total_unique} {dimension} values contribute to {metric}."

        # wallet concentration annotation
        wcr_note = ""
        if top_wcr > 1.2:
            wcr_note = (
                f", with a wallet concentration ratio of {round(float(top_wcr), 2)}"
                " indicating above-average transaction values"
            )
        elif top_wcr < 0.8 and top_wcr > 0:
            wcr_note = (
                f", with a wallet concentration ratio of {round(float(top_wcr), 2)}"
                " indicating high volume but lower-than-average transaction values"
            )

        key_finding = (
            f"{top_label} leads all {dimension} values with {top_val_str}"
            f" ({round(float(top_vol_share), 2)}% of total volume){wcr_note}."
        )

        return {
            "key_finding": key_finding,
            "top_performer": f"{top_label}: {top_val_str}",
            "bottom_performer": f"{bottom_label}: {bottom_val_str}",
            "most_concentrated_value": f"{most_conc_label} (ratio: {most_conc_ratio})",
            "pareto_statement": pareto_stmt,
        }

    # ==================================================================
    # Internal helpers — state regions
    # ==================================================================

    def _handle_state_regions(self, agg: pd.DataFrame) -> pd.DataFrame:
        """
        Add region, regional_rank, regional_share, and performance-vs-region
        columns for state data.

        Args:
            agg: Aggregated DataFrame with 'sender_state' as the dimension.

        Returns:
            DataFrame enriched with regional info.
        """
        agg = agg.copy()
        agg["region"] = agg["sender_state"].map(_STATE_REGION_MAP).fillna("Other")

        # regional rank by total_transactions within each region
        agg["regional_rank"] = (
            agg.groupby("region")["total_transactions"]
            .rank(ascending=False, method="min")
            .astype(int)
        )

        # regional share (state's volume / region volume)
        region_totals = agg.groupby("region")["total_transactions"].transform("sum")
        agg["regional_share_pct"] = np.where(
            region_totals > 0,
            np.round(agg["total_transactions"] / region_totals * 100, 2),
            0.0,
        )

        # vs regional average
        region_avg = agg.groupby("region")["total_transactions"].transform("mean")
        agg["state_vs_region_avg_pct"] = np.where(
            region_avg > 0,
            np.round((agg["total_transactions"] - region_avg) / region_avg * 100, 2),
            0.0,
        )

        return agg

    def _build_regional_summary(self, agg: pd.DataFrame) -> Dict[str, Any]:
        """
        Build an aggregate regional_summary block.

        Args:
            agg: Aggregated state DataFrame with 'region' column.

        Returns:
            Dict mapping region → aggregate metrics.
        """
        if "region" not in agg.columns:
            return {}
        summary: Dict[str, Any] = {}
        grand_total = agg["total_transactions"].sum()
        for region, grp in agg.groupby("region"):
            summary[str(region)] = {
                "states_count": int(len(grp)),
                "total_transactions": int(grp["total_transactions"].sum()),
                "total_amount": round(float(grp["total_amount"].sum()), 2),
                "avg_success_rate_pct": round(float(grp["success_rate_pct"].mean()), 2),
                "avg_fraud_rate_pct": round(float(grp["fraud_rate_pct"].mean()), 2),
                "volume_share_pct": round(
                    float(grp["total_transactions"].sum() / grand_total * 100) if grand_total else 0.0, 2
                ),
            }
        return summary

    # ==================================================================
    # Internal helpers — category enrichment
    # ==================================================================

    def _handle_category_enrichment(
        self, agg: pd.DataFrame, df_filtered: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Add category-specific enrichment: category_type, peak_hour,
        dominant_device, dominant_network, avg_basket_size, and
        category_fraud_premium.

        Args:
            agg: Aggregated DataFrame with 'merchant_category'.
            df_filtered: The filtered P2M DataFrame used for grouping.

        Returns:
            Enriched DataFrame.
        """
        agg = agg.copy()

        # category type
        agg["category_type"] = agg["merchant_category"].apply(
            lambda c: "Essential" if c in _ESSENTIAL_CATEGORIES
            else ("Discretionary" if c in _DISCRETIONARY_CATEGORIES else "Other")
        )

        # avg basket size (same as avg_amount, relabelled)
        agg["avg_basket_size"] = agg["avg_amount"]

        # p2m average fraud rate
        p2m_total = len(df_filtered)
        p2m_fraud = int(df_filtered["fraud_flag"].sum()) if p2m_total > 0 else 0
        p2m_avg_fraud = round(p2m_fraud / p2m_total * 100, 2) if p2m_total > 0 else 0.0
        agg["category_fraud_premium_pct"] = np.round(
            agg["fraud_rate_pct"] - p2m_avg_fraud, 2
        )

        # peak hour & dominant device/network per category
        peak_hours: List[Optional[int]] = []
        dominant_devices: List[str] = []
        dominant_networks: List[str] = []

        for cat in agg["merchant_category"]:
            cat_df = df_filtered[df_filtered["merchant_category"] == cat]
            if cat_df.empty:
                peak_hours.append(None)
                dominant_devices.append("N/A")
                dominant_networks.append("N/A")
                continue

            if "hour_of_day" in cat_df.columns:
                peak_hours.append(int(cat_df["hour_of_day"].mode().iloc[0]))
            else:
                peak_hours.append(None)

            if "device_type" in cat_df.columns:
                dominant_devices.append(str(cat_df["device_type"].mode().iloc[0]))
            else:
                dominant_devices.append("N/A")

            if "network_type" in cat_df.columns:
                dominant_networks.append(str(cat_df["network_type"].mode().iloc[0]))
            else:
                dominant_networks.append("N/A")

        agg["peak_hour"] = peak_hours
        agg["dominant_device"] = dominant_devices
        agg["dominant_network"] = dominant_networks

        return agg

    # ==================================================================
    # Item builder
    # ==================================================================

    def _build_ranked_item(
        self, row: pd.Series, dimension: str, extra: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Build one item dict for the ranked_items list.

        Args:
            row: A single row from the aggregated DataFrame.
            dimension: Dimension column name.
            extra: Optional additional fields to merge.

        Returns:
            Dictionary representing one ranked item.
        """
        item: Dict[str, Any] = {
            "rank": int(row["rank"]),
            "label": str(row[dimension]),
            "metrics": {
                "total_transactions": int(row["total_transactions"]),
                "share_of_total_volume_pct": round(float(row["share_of_total_volume_pct"]), 2),
                "total_amount": round(float(row["total_amount"]), 2),
                "avg_amount": round(float(row["avg_amount"]), 2),
                "median_amount": round(float(row["median_amount"]), 2),
                "share_of_total_amount_pct": round(float(row["share_of_total_amount_pct"]), 2),
                "wallet_concentration_ratio": round(float(row["wallet_concentration_ratio"]), 2),
                "success_rate_pct": round(float(row["success_rate_pct"]), 2),
                "failure_rate_pct": round(float(row["failure_rate_pct"]), 2),
                "pending_rate_pct": round(float(row["pending_rate_pct"]), 2),
                "fraud_rate_pct": round(float(row["fraud_rate_pct"]), 2),
                "fraud_by_value_rate_pct": round(float(row["fraud_by_value_rate_pct"]), 2),
            },
            "share_of_wallet": self._compute_share_of_wallet(row),
            "tier": str(row.get("tier", "")),
            "percentile": round(float(row.get("percentile", 0.0)), 2),
            "vs_average_pct": round(float(row.get("vs_dimension_average_pct", 0.0)), 2),
            "gap_to_rank_1": {
                "absolute": round(float(row.get("gap_to_rank_1_absolute", 0.0)), 2),
                "pct": round(float(row.get("gap_to_rank_1_pct", 0.0)), 2),
            },
        }
        if extra:
            item.update(extra)
        return item

    # ==================================================================
    # Response builders
    # ==================================================================

    def _success_response(
        self,
        ranking_type: str,
        dimension: str,
        metric: str,
        filters_applied: List[Dict],
        total_records_analyzed: int,
        total_unique: int,
        results_returned: int,
        ranked_items: List[Dict],
        pareto: Dict[str, Any],
        tier_summary: Dict[str, Any],
        summary: Dict[str, Any],
        excluded_nulls: int = 0,
        extra: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Build the standardised success JSON response.

        Args:
            ranking_type: Type of ranking performed.
            dimension: Column ranked on.
            metric: Primary metric used.
            filters_applied: Filter list.
            total_records_analyzed: Record count after filters.
            total_unique: Unique dimension values.
            results_returned: Items in ranked_items.
            ranked_items: The list of ranked item dicts.
            pareto: Pareto insights dict.
            tier_summary: Tier summary dict.
            summary: Summary dict.
            excluded_nulls: Number of null rows excluded.
            extra: Optional top-level extra fields.

        Returns:
            JSON string.
        """
        response: Dict[str, Any] = {
            "success": True,
            "ranking_type": ranking_type,
            "dimension": dimension,
            "metric": metric,
            "filters_applied": filters_applied,
            "total_records_analyzed": total_records_analyzed,
            "total_unique_values": total_unique,
            "results_returned": results_returned,
            "ranked_items": ranked_items,
            "pareto_insights": pareto,
            "tier_summary": tier_summary,
            "summary": summary,
            "metadata": {
                "data_coverage_pct": round(total_records_analyzed / self.total_records * 100, 2) if self.total_records else 0.0,
                "excluded_nulls": excluded_nulls,
                "execution_note": "Analysis completed successfully.",
            },
        }
        if extra:
            response.update(extra)
        return json.dumps(response, default=str)

    def _error_response(self, ranking_type: str, error: str, suggestion: str) -> str:
        """
        Build standardised error JSON response.

        Args:
            ranking_type: Type attempted.
            error: Error message.
            suggestion: Suggested fix.

        Returns:
            JSON string.
        """
        return json.dumps({
            "success": False,
            "ranking_type": ranking_type,
            "error": error,
            "suggestion": suggestion,
        })

    # ==================================================================
    # Common pre-processing for most ranking types
    # ==================================================================

    def _prepare_ranking(
        self, params: Dict[str, Any], default_metric: str = "volume"
    ) -> Tuple[pd.DataFrame, str, str, str, int, bool, int, List[str], List[Dict], int]:
        """
        Common pre-processing: validate dimension, apply filters, handle NULLs,
        compute group metrics.

        Args:
            params: Parameters dict.
            default_metric: Default metric if not provided.

        Returns:
            Tuple of (agg DataFrame, dimension, metric, sort_col, top_n,
            ascending, tier_count, tier_labels, filters, excluded_nulls).

        Raises:
            ValueError: If dimension is missing or invalid, or data is empty.
        """
        dimension: str = data_loader.resolve_column(params.get("dimension", ""))
        metric: str = params.get("metric", default_metric)
        top_n: int = int(params.get("top_n", 10))
        ascending: bool = bool(params.get("ascending", False))
        tier_count: int = int(params.get("tier_count", 3))
        tier_labels: List[str] = params.get("tier_labels", ["Top Tier", "Mid Tier", "Low Tier"])
        filters: List[Dict] = params.get("filters", [])

        if not dimension:
            raise ValueError("'dimension' parameter is required.")
        if dimension not in self.df.columns:
            raise ValueError(
                f"Column '{dimension}' not found. Available: {list(self.df.columns)}"
            )

        df = self._apply_filters(self.df.copy(), filters)
        if df.empty:
            raise ValueError("No data remaining after applying filters.")

        # Exclude NULLs on dimension
        excluded_nulls = int(df[dimension].isna().sum())
        if excluded_nulls > 0:
            df = df[df[dimension].notna()]
        if df.empty:
            raise ValueError(
                f"All rows have NULL '{dimension}' after filtering."
            )

        sort_col = self._get_sort_column(metric)
        agg = self._compute_group_metrics(df, dimension)
        agg = self._add_ranking_fields(agg, sort_col, ascending)
        agg = self._assign_tiers(agg, tier_count, tier_labels)

        # If dimension is sender_state, always add regional info
        if dimension == "sender_state":
            agg = self._handle_state_regions(agg)

        return agg, dimension, metric, sort_col, top_n, ascending, tier_count, tier_labels, filters, excluded_nulls

    # ==================================================================
    # Ranking type implementations
    # ==================================================================

    def _rank_top_n(self, params: Dict[str, Any]) -> str:
        """
        Rank all dimension values by a metric, return top N.

        Args:
            params: Parameters dict with dimension, metric, top_n, filters, etc.

        Returns:
            JSON string with top-N ranking results.
        """
        agg, dimension, metric, sort_col, top_n, ascending, tc, tl, filters, excl = (
            self._prepare_ranking(params)
        )
        total_unique = len(agg)
        top = agg.head(top_n)

        ranked_items = [self._build_ranked_item(row, dimension) for _, row in top.iterrows()]
        pareto = self._compute_pareto_insights(agg, sort_col)
        tier_summary = self._build_tier_summary(agg, sort_col)
        summary = self._generate_summary(agg, dimension, sort_col, metric, pareto)

        extra: Optional[Dict[str, Any]] = None
        if dimension == "sender_state" and "region" in agg.columns:
            extra = {"regional_summary": self._build_regional_summary(agg)}
            for item, (_, row) in zip(ranked_items, top.iterrows()):
                item["region"] = str(row.get("region", ""))
                item["regional_rank"] = int(row.get("regional_rank", 0))
                item["regional_share_pct"] = round(float(row.get("regional_share_pct", 0.0)), 2)

        return self._success_response(
            "top_n", dimension, metric, filters, int(agg["total_transactions"].sum()),
            total_unique, len(ranked_items), ranked_items, pareto, tier_summary, summary,
            excl, extra,
        )

    def _rank_bottom_n(self, params: Dict[str, Any]) -> str:
        """
        Rank dimension values, return bottom N (worst performers).

        Args:
            params: Parameters dict.

        Returns:
            JSON string with bottom-N ranking results including concern levels.
        """
        # Force ascending for bottom
        params = {**params, "ascending": True}
        agg, dimension, metric, sort_col, top_n, ascending, tc, tl, filters, excl = (
            self._prepare_ranking(params)
        )
        total_unique = len(agg)
        bottom = agg.head(top_n)

        # gap_to_average and concern_level
        dim_avg = float(agg[sort_col].mean())
        dim_std = float(agg[sort_col].std()) if len(agg) > 1 else 0.0

        ranked_items = []
        for _, row in bottom.iterrows():
            val = float(row[sort_col])
            gap = round(val - dim_avg, 2)
            if dim_std > 0:
                z = (val - dim_avg) / dim_std
                if z < -2:
                    concern = "Critical"
                elif z < -1:
                    concern = "Warning"
                else:
                    concern = "Moderate"
            else:
                concern = "Moderate"

            item = self._build_ranked_item(row, dimension, extra={
                "gap_to_average": gap,
                "concern_level": concern,
            })
            ranked_items.append(item)

        pareto = self._compute_pareto_insights(agg, sort_col)
        tier_summary = self._build_tier_summary(agg, sort_col)
        summary = self._generate_summary(agg, dimension, sort_col, metric, pareto)
        # Override key finding for bottom
        if ranked_items:
            worst = ranked_items[0]
            summary["key_finding"] = (
                f"{worst['label']} is the worst performer among {dimension} values"
                f" with {worst['metrics'].get(sort_col, worst['metrics'].get('total_transactions', 'N/A'))}"
                f" ({worst.get('concern_level', 'N/A')} concern level)."
            )

        extra_resp: Optional[Dict[str, Any]] = None
        if dimension == "sender_state" and "region" in agg.columns:
            extra_resp = {"regional_summary": self._build_regional_summary(agg)}
            for item, (_, row) in zip(ranked_items, bottom.iterrows()):
                item["region"] = str(row.get("region", ""))
                item["regional_rank"] = int(row.get("regional_rank", 0))

        return self._success_response(
            "bottom_n", dimension, metric, filters, int(agg["total_transactions"].sum()),
            total_unique, len(ranked_items), ranked_items, pareto, tier_summary, summary,
            excl, extra_resp,
        )

    def _rank_full(self, params: Dict[str, Any]) -> str:
        """
        Complete ranked list of all unique dimension values.

        Args:
            params: Parameters dict.

        Returns:
            JSON string with full ranking, percentiles, and tiers.
        """
        agg, dimension, metric, sort_col, _, ascending, tc, tl, filters, excl = (
            self._prepare_ranking(params)
        )
        total_unique = len(agg)
        ranked_items = [self._build_ranked_item(row, dimension) for _, row in agg.iterrows()]

        pareto = self._compute_pareto_insights(agg, sort_col)
        tier_summary = self._build_tier_summary(agg, sort_col)
        summary = self._generate_summary(agg, dimension, sort_col, metric, pareto)

        extra: Optional[Dict[str, Any]] = None
        if dimension == "sender_state" and "region" in agg.columns:
            extra = {"regional_summary": self._build_regional_summary(agg)}
            for item, (_, row) in zip(ranked_items, agg.iterrows()):
                item["region"] = str(row.get("region", ""))
                item["regional_rank"] = int(row.get("regional_rank", 0))
                item["regional_share_pct"] = round(float(row.get("regional_share_pct", 0.0)), 2)

        return self._success_response(
            "full_ranking", dimension, metric, filters, int(agg["total_transactions"].sum()),
            total_unique, len(ranked_items), ranked_items, pareto, tier_summary, summary,
            excl, extra,
        )

    def _rank_share_of_wallet(self, params: Dict[str, Any]) -> str:
        """
        Share-of-wallet analysis focused on transaction value distribution.

        Args:
            params: Parameters dict.

        Returns:
            JSON string with amount-share ranking and wallet concentration.
        """
        # Force metric to total_amount
        params = {**params, "metric": "total_amount"}
        agg, dimension, metric, sort_col, top_n, ascending, tc, tl, filters, excl = (
            self._prepare_ranking(params)
        )
        total_unique = len(agg)

        # Pareto on amount
        desc = agg.sort_values("total_amount", ascending=False).reset_index(drop=True)
        grand_amount = desc["total_amount"].sum()
        cum_amt = (desc["total_amount"].cumsum() / grand_amount * 100).round(2) if grand_amount else pd.Series([0.0] * len(desc))
        pareto_80_labels: List[str] = []
        for i, share in enumerate(cum_amt):
            pareto_80_labels.append(str(desc.loc[i, dimension]))
            if share >= 80:
                break

        ranked_items = []
        for _, row in agg.iterrows():
            wcr = float(row["wallet_concentration_ratio"])
            extra_fields = {
                "amount_share_pct": round(float(row["share_of_total_amount_pct"]), 2),
                "volume_share_pct": round(float(row["share_of_total_volume_pct"]), 2),
                "wallet_concentration_ratio": round(wcr, 2),
                "wallet_concentration_label": (
                    "High-Value Segment" if wcr > 1.2
                    else ("Balanced" if wcr >= 0.8 else "High-Volume Low-Value Segment")
                ),
                "avg_transaction_value": round(float(row["avg_amount"]), 2),
                "in_pareto_80": str(row[dimension]) in pareto_80_labels,
            }
            ranked_items.append(self._build_ranked_item(row, dimension, extra_fields))

        pareto = self._compute_pareto_insights(agg, "total_amount")
        tier_summary = self._build_tier_summary(agg, "total_amount")
        summary = self._generate_summary(agg, dimension, "total_amount", "total_amount", pareto)

        extra_resp: Optional[Dict[str, Any]] = None
        if dimension == "sender_state" and "region" in agg.columns:
            extra_resp = {"regional_summary": self._build_regional_summary(agg)}

        return self._success_response(
            "share_of_wallet", dimension, "total_amount", filters,
            int(agg["total_transactions"].sum()), total_unique,
            len(ranked_items), ranked_items, pareto, tier_summary, summary,
            excl, extra_resp,
        )

    def _rank_fraud(self, params: Dict[str, Any]) -> str:
        """
        Specialized fraud ranking with volume context and risk scoring.

        Args:
            params: Parameters dict.

        Returns:
            JSON string with fraud ranking, risk scores, and flags.
        """
        params = {**params, "metric": "fraud_rate"}
        agg, dimension, metric, sort_col, top_n, ascending, tc, tl, filters, excl = (
            self._prepare_ranking(params)
        )
        total_unique = len(agg)

        overall_fraud_rate = float(agg["fraud_count"].sum() / agg["total_transactions"].sum() * 100) if agg["total_transactions"].sum() > 0 else 0.0

        ranked_items = []
        for _, row in agg.iterrows():
            fraud_rate = float(row["fraud_rate_pct"])
            total_txn = int(row["total_transactions"])
            fraud_count = int(row["fraud_count"])

            # expected fraud (at average rate)
            expected = round(total_txn * overall_fraud_rate / 100, 2)

            # fraud risk score: (fraud_rate / overall) × log(total_txn)
            log_vol = math.log(max(total_txn, 1))
            risk_score = round(
                (fraud_rate / overall_fraud_rate * log_vol) if overall_fraud_rate > 0 else 0.0, 2
            )

            high_risk = fraud_rate > 2 * overall_fraud_rate

            extra_fields = {
                "fraud_volume_context": {
                    "fraud_count": fraud_count,
                    "total_transactions": total_txn,
                    "fraud_rate_pct": round(fraud_rate, 2),
                    "fraud_by_value_rate_pct": round(float(row["fraud_by_value_rate_pct"]), 2),
                },
                "expected_fraud_count": expected,
                "actual_vs_expected": round(fraud_count - expected, 2),
                "fraud_risk_score": risk_score,
                "high_risk": high_risk,
                "overall_fraud_rate_pct": round(overall_fraud_rate, 2),
            }
            ranked_items.append(self._build_ranked_item(row, dimension, extra_fields))

        pareto = self._compute_pareto_insights(agg, "fraud_count")
        tier_summary = self._build_tier_summary(agg, sort_col)
        summary = self._generate_summary(agg, dimension, sort_col, metric, pareto)

        # Enhance key finding for fraud context
        if ranked_items:
            top = ranked_items[0]
            summary["key_finding"] = (
                f"{top['label']} has the highest fraud rate at"
                f" {top['fraud_volume_context']['fraud_rate_pct']}%"
                f" with {top['fraud_volume_context']['fraud_count']} flagged transactions"
                f" (risk score: {top['fraud_risk_score']})."
                f" {'HIGH RISK: rate exceeds 2× the overall average.' if top['high_risk'] else ''}"
            )

        return self._success_response(
            "fraud_ranking", dimension, "fraud_rate", filters,
            int(agg["total_transactions"].sum()), total_unique,
            len(ranked_items), ranked_items, pareto, tier_summary, summary,
            excl,
        )

    def _rank_failure(self, params: Dict[str, Any]) -> str:
        """
        Specialized failure ranking with volume impact and recovery potential.

        Args:
            params: Parameters dict.

        Returns:
            JSON string with failure ranking, impact scores, and recovery estimates.
        """
        params = {**params, "metric": "failure_rate"}
        agg, dimension, metric, sort_col, top_n, ascending, tc, tl, filters, excl = (
            self._prepare_ranking(params)
        )
        total_unique = len(agg)

        overall_failure_rate = float(
            agg["failed_count"].sum() / agg["total_transactions"].sum() * 100
        ) if agg["total_transactions"].sum() > 0 else 0.0

        best_failure_rate = float(agg["failure_rate_pct"].min())

        ranked_items = []
        for _, row in agg.iterrows():
            failure_rate = float(row["failure_rate_pct"])
            total_txn = int(row["total_transactions"])
            failed_count = int(row["failed_count"])
            avg_amt = float(row["avg_amount"])

            # failure impact score
            log_vol = math.log(max(total_txn, 1))
            impact_score = round(failure_rate * log_vol, 2)

            # estimated revenue impact
            revenue_impact = round(failed_count * avg_amt, 2)

            # recovery potential (bring to best performer's rate)
            current_failures = failed_count
            expected_at_best = round(total_txn * best_failure_rate / 100)
            recovery = max(current_failures - expected_at_best, 0)

            high_concern = failure_rate > 1.5 * overall_failure_rate

            extra_fields = {
                "failure_volume": failed_count,
                "failure_impact_score": impact_score,
                "estimated_revenue_impact_inr": revenue_impact,
                "recovery_potential_transactions": recovery,
                "high_concern": high_concern,
                "overall_failure_rate_pct": round(overall_failure_rate, 2),
                "best_failure_rate_pct": round(best_failure_rate, 2),
            }
            ranked_items.append(self._build_ranked_item(row, dimension, extra_fields))

        pareto = self._compute_pareto_insights(agg, "failed_count")
        tier_summary = self._build_tier_summary(agg, sort_col)
        summary = self._generate_summary(agg, dimension, sort_col, metric, pareto)

        if ranked_items:
            top = ranked_items[0]
            summary["key_finding"] = (
                f"{top['label']} has the highest failure rate at"
                f" {top['metrics']['failure_rate_pct']}%"
                f" with {top['failure_volume']} failed transactions"
                f" (est. revenue impact: ₹{top['estimated_revenue_impact_inr']:,.2f})."
                f" {top['recovery_potential_transactions']} additional successes possible"
                f" if brought to best rate of {top['best_failure_rate_pct']}%."
            )

        return self._success_response(
            "failure_ranking", dimension, "failure_rate", filters,
            int(agg["total_transactions"].sum()), total_unique,
            len(ranked_items), ranked_items, pareto, tier_summary, summary,
            excl,
        )

    def _rank_multi_metric(self, params: Dict[str, Any]) -> str:
        """
        Composite ranking across multiple weighted metrics.

        Args:
            params: Parameters dict; requires composite_weights.

        Returns:
            JSON string with composite scores and per-metric breakdowns.
        """
        dimension: str = data_loader.resolve_column(params.get("dimension", ""))
        composite_weights: Dict[str, float] = params.get("composite_weights", {})
        filters: List[Dict] = params.get("filters", [])
        tier_count: int = int(params.get("tier_count", 3))
        tier_labels: List[str] = params.get("tier_labels", ["Top Tier", "Mid Tier", "Low Tier"])

        if not composite_weights:
            return self._error_response(
                "multi_metric_ranking",
                "composite_weights parameter is required.",
                "Provide e.g. {\"volume\": 0.4, \"failure_rate\": -0.3, \"avg_amount\": 0.3}",
            )
        if not dimension:
            return self._error_response(
                "multi_metric_ranking",
                "'dimension' parameter is required.",
                "Specify the column to rank, e.g. 'sender_bank'.",
            )
        if dimension not in self.df.columns:
            return self._error_response(
                "multi_metric_ranking",
                f"Column '{dimension}' not found.",
                f"Available columns: {list(self.df.columns)}",
            )

        df = self._apply_filters(self.df.copy(), filters)
        if df.empty:
            return self._error_response(
                "multi_metric_ranking", "No data after filters.", "Broaden filters.",
            )

        excluded_nulls = int(df[dimension].isna().sum())
        df = df[df[dimension].notna()]
        if df.empty:
            return self._error_response(
                "multi_metric_ranking",
                f"All rows have NULL '{dimension}'.",
                "Choose a different dimension.",
            )

        agg = self._compute_group_metrics(df, dimension)

        # Map metric names to columns
        metric_col_map: Dict[str, str] = {}
        for m in composite_weights:
            col = self._get_sort_column(m)
            if col in agg.columns:
                metric_col_map[m] = col
            else:
                return self._error_response(
                    "multi_metric_ranking",
                    f"Metric '{m}' maps to unknown column '{col}'.",
                    f"Available: {list(agg.columns)}",
                )

        # Min-max normalisation per metric, invert for negative weights
        norm_cols: Dict[str, str] = {}
        for m, col in metric_col_map.items():
            vals = agg[col].astype(float)
            vmin, vmax = vals.min(), vals.max()
            if vmax - vmin > 0:
                normed = (vals - vmin) / (vmax - vmin) * 100
            else:
                normed = pd.Series(50.0, index=agg.index)
            weight = composite_weights[m]
            if weight < 0:
                normed = 100 - normed  # invert — lower is better
            norm_col_name = f"_norm_{m}"
            agg[norm_col_name] = np.round(normed, 2)
            norm_cols[m] = norm_col_name

        # Composite score
        abs_weights = {m: abs(w) for m, w in composite_weights.items()}
        agg["composite_score"] = 0.0
        for m, norm_col in norm_cols.items():
            agg["composite_score"] += agg[norm_col] * abs_weights[m]
        agg["composite_score"] = np.round(agg["composite_score"], 2)

        # Rank by composite
        agg = agg.sort_values("composite_score", ascending=False).reset_index(drop=True)
        agg["rank"] = range(1, len(agg) + 1)

        total_items = len(agg)
        if total_items > 1:
            agg["percentile"] = np.round(
                (1 - (agg["rank"] - 1) / (total_items - 1)) * 100, 2
            )
        else:
            agg["percentile"] = 100.0

        # cumulative shares
        cum_vol = agg["share_of_total_volume_pct"].cumsum().round(2)
        cum_amt = agg["share_of_total_amount_pct"].cumsum().round(2)
        agg["cumulative_volume_share_pct"] = cum_vol
        agg["cumulative_amount_share_pct"] = cum_amt
        agg["vs_dimension_average_pct"] = 0.0
        agg["gap_to_rank_1_absolute"] = np.round(
            agg["composite_score"].iloc[0] - agg["composite_score"], 2
        )
        agg["gap_to_rank_1_pct"] = np.where(
            agg["composite_score"].iloc[0] != 0,
            np.round(
                (agg["composite_score"].iloc[0] - agg["composite_score"])
                / abs(agg["composite_score"].iloc[0]) * 100, 2
            ),
            0.0,
        )
        agg = self._assign_tiers(agg, tier_count, tier_labels)

        # Per-metric individual ranks
        individual_ranks: Dict[str, Dict[str, int]] = {}
        for m, col in metric_col_map.items():
            w = composite_weights[m]
            asc = w < 0  # negative weight means lower is better
            rank_series = agg[col].rank(ascending=asc, method="min").astype(int)
            for idx, (_, row) in enumerate(agg.iterrows()):
                label = str(row[dimension])
                individual_ranks.setdefault(label, {})[f"{m}_rank"] = int(rank_series.iloc[idx])

        ranked_items = []
        for _, row in agg.iterrows():
            label = str(row[dimension])
            score_breakdown = {}
            for m, norm_col in norm_cols.items():
                score_breakdown[m] = {
                    "normalized_score": round(float(row[norm_col]), 2),
                    "weight": composite_weights[m],
                    "contribution": round(float(row[norm_col]) * abs(composite_weights[m]), 2),
                }
            extra_fields = {
                "composite_score": round(float(row["composite_score"]), 2),
                "composite_rank": int(row["rank"]),
                "score_breakdown": score_breakdown,
                "individual_metric_ranks": individual_ranks.get(label, {}),
            }
            ranked_items.append(self._build_ranked_item(row, dimension, extra_fields))

        pareto = self._compute_pareto_insights(agg, "composite_score")
        tier_summary = self._build_tier_summary(agg, "composite_score")

        # summary
        top_item = ranked_items[0] if ranked_items else None
        key_finding = "No data available." if not top_item else (
            f"{top_item['label']} ranks #1 overall with a composite score of"
            f" {top_item['composite_score']}"
            f" ({top_item['metrics']['share_of_total_volume_pct']}% volume share)."
        )
        summary_dict = {
            "key_finding": key_finding,
            "top_performer": f"{top_item['label']}: score {top_item['composite_score']}" if top_item else "N/A",
            "bottom_performer": (
                f"{ranked_items[-1]['label']}: score {ranked_items[-1]['composite_score']}"
                if ranked_items else "N/A"
            ),
            "most_concentrated_value": "N/A",
            "pareto_statement": f"Composite ranking across {len(composite_weights)} metrics for {len(agg)} {dimension} values.",
        }

        return self._success_response(
            "multi_metric_ranking", dimension, "composite", filters,
            int(agg["total_transactions"].sum()), total_items,
            len(ranked_items), ranked_items, pareto, tier_summary, summary_dict,
            excluded_nulls,
        )

    def _rank_pareto(self, params: Dict[str, Any]) -> str:
        """
        Pareto / 80-20 concentration analysis.

        Args:
            params: Parameters dict.

        Returns:
            JSON string with Pareto thresholds, segment classification, and HHI.
        """
        agg, dimension, metric, sort_col, _, ascending, tc, tl, filters, excl = (
            self._prepare_ranking(params)
        )
        total_unique = len(agg)

        # sort descending by metric for Pareto
        desc = agg.sort_values(sort_col, ascending=False).reset_index(drop=True)
        metric_total = desc[sort_col].sum()

        if metric_total > 0:
            cum_share = (desc[sort_col].cumsum() / metric_total * 100).round(2)
        else:
            cum_share = pd.Series([0.0] * len(desc))

        # classify
        classifications: List[str] = []
        for cs in cum_share:
            if cs <= 80:
                classifications.append("Core")
            elif cs <= 95:
                classifications.append("Peripheral")
            else:
                classifications.append("Tail")
        desc["pareto_class"] = classifications
        desc["cumulative_metric_share_pct"] = cum_share.values

        # pareto ratio
        core_count = sum(1 for c in classifications if c == "Core")
        pareto_ratio = round(core_count / total_unique * 100, 2) if total_unique else 0.0

        # re-apply ranks from original order
        desc["rank"] = range(1, len(desc) + 1)
        # re-set percentile
        if total_unique > 1:
            desc["percentile"] = np.round(
                (1 - (desc["rank"] - 1) / (total_unique - 1)) * 100, 2
            )
        else:
            desc["percentile"] = 100.0

        ranked_items = []
        for _, row in desc.iterrows():
            extra_fields = {
                "pareto_class": str(row["pareto_class"]),
                "cumulative_metric_share_pct": round(float(row["cumulative_metric_share_pct"]), 2),
            }
            ranked_items.append(self._build_ranked_item(row, dimension, extra_fields))

        pareto = self._compute_pareto_insights(agg, sort_col)
        pareto["pareto_ratio_pct"] = pareto_ratio

        tier_summary_dict: Dict[str, Any] = {}
        for cls in ("Core", "Peripheral", "Tail"):
            cls_items = [r for r in ranked_items if r.get("pareto_class") == cls]
            cls_count = len(cls_items)
            cls_share = sum(it["share_of_wallet"]["volume_share_pct"] for it in cls_items)
            tier_summary_dict[cls] = {
                "count": cls_count,
                "combined_share_pct": round(cls_share, 2),
                "avg_metric_value": round(
                    sum(it["metrics"].get(sort_col, it["metrics"]["total_transactions"]) for it in cls_items) / max(cls_count, 1), 2
                ),
            }

        summary = self._generate_summary(agg, dimension, sort_col, metric, pareto)
        # enhance pareto statement
        if core_count and total_unique:
            core_labels = [r["label"] for r in ranked_items if r.get("pareto_class") == "Core"]
            core_share = round(
                sum(r["share_of_wallet"]["volume_share_pct"] for r in ranked_items if r.get("pareto_class") == "Core"), 2
            )
            summary["pareto_statement"] = (
                f"Top {core_count} {dimension} values ({', '.join(core_labels[:5])}"
                f"{'...' if len(core_labels) > 5 else ''})"
                f" account for {core_share}% of total {metric}."
            )

        extra_resp: Optional[Dict[str, Any]] = None
        if dimension == "sender_state" and "region" in agg.columns:
            extra_resp = {"regional_summary": self._build_regional_summary(agg)}

        return self._success_response(
            "pareto_analysis", dimension, metric, filters,
            int(agg["total_transactions"].sum()), total_unique,
            len(ranked_items), ranked_items, pareto, tier_summary_dict, summary,
            excl, extra_resp,
        )

    def _rank_state(self, params: Dict[str, Any]) -> str:
        """
        Specialized deep ranking for sender_state with regional grouping.

        Args:
            params: Parameters dict.

        Returns:
            JSON string with state ranking, regional enrichment, and summary.
        """
        params = {**params, "dimension": "sender_state"}
        agg, dimension, metric, sort_col, top_n, ascending, tc, tl, filters, excl = (
            self._prepare_ranking(params)
        )
        total_unique = len(agg)

        ranked_items = []
        for _, row in agg.iterrows():
            extra_fields = {
                "region": str(row.get("region", "")),
                "national_rank": int(row["rank"]),
                "regional_rank": int(row.get("regional_rank", 0)),
                "regional_share_pct": round(float(row.get("regional_share_pct", 0.0)), 2),
                "state_performance_vs_region_pct": round(float(row.get("state_vs_region_avg_pct", 0.0)), 2),
            }
            ranked_items.append(self._build_ranked_item(row, dimension, extra_fields))

        pareto = self._compute_pareto_insights(agg, sort_col)
        tier_summary = self._build_tier_summary(agg, sort_col)
        summary = self._generate_summary(agg, dimension, sort_col, metric, pareto)

        extra_resp = {"regional_summary": self._build_regional_summary(agg)}

        return self._success_response(
            "state_ranking", dimension, metric, filters,
            int(agg["total_transactions"].sum()), total_unique,
            len(ranked_items), ranked_items, pareto, tier_summary, summary,
            excl, extra_resp,
        )

    def _rank_category(self, params: Dict[str, Any]) -> str:
        """
        Specialized deep ranking for merchant_category (P2M only).

        Args:
            params: Parameters dict.

        Returns:
            JSON string with category ranking, enrichment, and P2M context.
        """
        params = {**params, "dimension": "merchant_category"}
        metric: str = params.get("metric", "volume")
        top_n: int = int(params.get("top_n", 10))
        ascending: bool = bool(params.get("ascending", False))
        tier_count: int = int(params.get("tier_count", 3))
        tier_labels: List[str] = params.get("tier_labels", ["Top Tier", "Mid Tier", "Low Tier"])
        filters: List[Dict] = params.get("filters", [])

        df = self._apply_filters(self.df.copy(), filters)
        if df.empty:
            return self._error_response(
                "category_ranking", "No data after filters.", "Broaden filters.",
            )

        # Filter to P2M only (exclude null merchant_category)
        excluded_nulls = int(df["merchant_category"].isna().sum())
        df = df[df["merchant_category"].notna()]
        if df.empty:
            return self._error_response(
                "category_ranking",
                "No P2M transactions remaining.",
                "Remove conflicting filters.",
            )

        sort_col = self._get_sort_column(metric)
        agg = self._compute_group_metrics(df, "merchant_category")
        agg = self._add_ranking_fields(agg, sort_col, ascending)
        agg = self._assign_tiers(agg, tier_count, tier_labels)
        agg = self._handle_category_enrichment(agg, df)

        total_unique = len(agg)

        ranked_items = []
        for _, row in agg.iterrows():
            extra_fields = {
                "category_type": str(row.get("category_type", "")),
                "peak_hour": int(row["peak_hour"]) if row.get("peak_hour") is not None else None,
                "dominant_device": str(row.get("dominant_device", "")),
                "dominant_network": str(row.get("dominant_network", "")),
                "avg_basket_size": round(float(row.get("avg_basket_size", 0.0)), 2),
                "category_fraud_premium_pct": round(float(row.get("category_fraud_premium_pct", 0.0)), 2),
            }
            ranked_items.append(self._build_ranked_item(row, "merchant_category", extra_fields))

        pareto = self._compute_pareto_insights(agg, sort_col)
        tier_summary = self._build_tier_summary(agg, sort_col)
        summary = self._generate_summary(agg, "merchant_category", sort_col, metric, pareto)

        return self._success_response(
            "category_ranking", "merchant_category", metric, filters,
            int(agg["total_transactions"].sum()), total_unique,
            len(ranked_items), ranked_items, pareto, tier_summary, summary,
            excluded_nulls,
        )


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------

def create_ranking_tool() -> StructuredTool:
    """
    Factory function to create the ranking tool for LangChain.

    Returns:
        StructuredTool configured for ranking and leaderboard analysis.
    """
    tool_instance = RankingTool()

    return StructuredTool.from_function(
        func=tool_instance.rank,
        name="ranking_tool",
        description=(
            "For ALL ranking, leaderboard, top-N, bottom-N, and share-of-total questions. "
            "Use this when the user asks 'which is most/least', 'top N', 'rank by', "
            "'which has highest/lowest', 'share of', or 'who leads in'. "
            "Covers state rankings, bank rankings, merchant category rankings, device rankings, "
            "age group rankings. Input: ranking_type (string: top_n, bottom_n, full_ranking, "
            "share_of_wallet, fraud_ranking, failure_ranking, multi_metric_ranking, "
            "pareto_analysis, state_ranking, category_ranking) and parameters (JSON string "
            "with dimension, metric, top_n, filters, include_pareto, tier_count, "
            "composite_weights)."
        ),
        args_schema=RankingInput,
    )
